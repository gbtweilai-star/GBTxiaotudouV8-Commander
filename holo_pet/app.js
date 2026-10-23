const MAX_TIMELINE_ITEMS = 90;
const MAX_TIMELINE_DETAIL = 180;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const shell = $("#holo-shell");
const timeline = $("#timeline");
const composer = $("#composer");
const input = $("#input");
const sendButton = $("#btn-send");
const approvalHost = $("#approval-host");
const toastStack = $("#toast-stack");
const dragHandle = $("#drag-handle");
const voiceRipple = $("#voice-ripple");
const microphoneButton = $("#btn-mic");
const voiceOutputButton = $("#btn-voice-output");
const senseDetail = $("#sense-detail");
const senseDetailCode = $("#sense-detail-code");
const senseDetailTitle = $("#sense-detail-title");
const senseDetailSummary = $("#sense-detail-summary");
const senseDetailMetrics = $("#sense-detail-metrics");
const senseDetailClose = $("#sense-detail-close");

const SENSE_META = {
  brain: { code: "MIND", title: "脑 · 心智模型" },
  eye: { code: "VISION", title: "眼 · 原生视觉" },
  ear: { code: "HEARING", title: "耳 · 语音输入" },
  mouth: { code: "EXPRESSION", title: "嘴 · 语音表达" },
  hand: { code: "EXECUTION", title: "手 · 触手执行" },
};

const app = {
  eventSource: null,
  assistantNode: null,
  thinking: false,
  lastUserText: "",
  selectedCharacteristic: null,
  pendingWrite: null,
  bluetoothBusy: false,
  notionBusy: false,
  eigenfluxBusy: false,
  eigenfluxTab: "feed",
  eigenfluxFriends: [],
  eigenfluxSnapshot: {},
  speechOutput: false,
  recognizer: null,
  recognitionActive: false,
  voiceConversation: false,
  speaking: false,
  voiceRestartTimer: null,
  drag: null,
  mood: "calm",
  sensory: {},
  selectedSense: "",
  sensePulseTimers: new Map(),
};

function setAvatarStatus(text, tone = "warn") {
  $("#avatar-status").textContent = text;
  const dot = $("#avatar-dot");
  dot.classList.remove("is-live", "is-warn", "is-error");
  dot.classList.add(`is-${tone}`);
}

function setThinking(active) {
  app.thinking = Boolean(active);
  const state = $("#thinking-state");
  state.textContent = app.thinking ? "执行中" : "待命";
  state.classList.toggle("is-thinking", app.thinking);
  setLocalAvatarState(app.thinking ? "thinking" : "idle");
}

function nowLabel() {
  return new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function scrollTimelineToBottom() {
  const scroller = timeline;
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
}

function trimTimeline() {
  const rows = $$(".timeline-item", timeline);
  if (rows.length > MAX_TIMELINE_ITEMS) {
    rows.slice(0, rows.length - MAX_TIMELINE_ITEMS).forEach((row) => row.remove());
  }
}

function addTimeline(title, detail = "", kind = "system", active = false) {
  const li = document.createElement("li");
  li.className = "timeline-item";
  li.dataset.kind = kind;
  if (active) li.classList.add("is-active");
  if (kind === "error") li.classList.add("is-error");

  const node = document.createElement("span");
  node.className = "timeline-node";
  const copy = document.createElement("div");
  const strong = document.createElement("strong");
  const small = document.createElement("small");
  strong.textContent = String(title || "状态更新");
  const summary = String(detail || nowLabel()).replace(/\s+/g, " ").trim();
  small.textContent = summary.length > MAX_TIMELINE_DETAIL
    ? `${summary.slice(0, MAX_TIMELINE_DETAIL - 1)}…`
    : summary;
  copy.append(strong, small);
  li.append(node, copy);
  timeline.appendChild(li);
  trimTimeline();
  scrollTimelineToBottom();
}

function addMessage(role, text, options = {}) {
  const message = document.createElement("div");
  message.className = `message message--${role}`;

  const meta = document.createElement("div");
  meta.className = "message__meta";
  const name = document.createElement("span");
  name.textContent = role === "user" ? "你" : "小土豆";
  const time = document.createElement("span");
  time.textContent = options.label || nowLabel();
  meta.append(name, time);

  const body = document.createElement("p");
  body.className = "message__text";
  body.textContent = String(text || "");
  message.append(meta, body);
  timeline.appendChild(message);
  trimTimeline();
  scrollTimelineToBottom();
  return body;
}

function appendAssistantDelta(piece) {
  if (!piece) return;
  if (!app.assistantNode) {
    app.assistantNode = addMessage("assistant", "");
  }
  app.assistantNode.textContent += piece;
  scrollTimelineToBottom();
}

function finishAssistant(text = "") {
  if (app.assistantNode) {
    if (String(text || "").trim()) app.assistantNode.textContent = String(text);
    const finalText = app.assistantNode.textContent.trim();
    if (finalText) {
      pulseSense("mouth", 1800);
      xingyun.lastReply = finalText;
      speakIfEnabled(finalText);
    }
    app.assistantNode = null;
    return;
  }
  if (String(text || "").trim()) {
    addMessage("assistant", text);
    pulseSense("mouth", 1800);
    xingyun.lastReply = String(text);
    speakIfEnabled(text);
  }
}

function toast(message, tone = "info", timeout = 3600) {
  const item = document.createElement("div");
  item.className = `toast${tone === "error" ? " toast--error" : tone === "success" ? " toast--success" : ""}`;
  item.textContent = String(message || "");
  toastStack.appendChild(item);
  window.setTimeout(() => item.remove(), timeout);
}

function glitch() {
  document.body.classList.remove("is-glitch");
  void document.body.offsetWidth;
  document.body.classList.add("is-glitch");
  window.setTimeout(() => document.body.classList.remove("is-glitch"), 460);
}

function compactResult(result) {
  if (result == null) return "";
  if (typeof result === "string") return result.slice(0, 300);
  if (typeof result !== "object") return String(result).slice(0, 300);
  const preferred = result.detail || result.error || result.note || result.message || result.status;
  if (preferred) return String(preferred).slice(0, 300);
  try {
    return JSON.stringify(result).slice(0, 300);
  } catch {
    return String(result).slice(0, 300);
  }
}

function normalizeCapabilityResult(value) {
  let result = value && typeof value === "object" ? value : {};
  if (result.kind && result.status && result.result && typeof result.result === "object") {
    result = result.result;
  }
  return result;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `请求失败（${response.status}）`);
  }
  return data;
}

function safeLastError(text) {
  const serverSafe = typeof text === "string" ? text.trim() : "";
  if (!serverSafe) return "";
  let asciiSeen = false;
  for (let i = 0; i < serverSafe.length; i += 1) {
    const code = serverSafe.charCodeAt(i);
    if ((code >= 65 && code <= 90) || (code >= 97 && code <= 122)) {
      asciiSeen = true;
      break;
    }
  }
  if (!asciiSeen) return serverSafe;
  return serverSafe.replace(/[A-Za-z][A-Za-z0-9_.-]*/g, "…");
}

function safeLastErrorOr(text, fallback) {
  const safe = safeLastError(text);
  return safe && !safe.includes("…") ? safe : fallback;
}

function updateCodexStatus(state) {
  const codex = state?.codex || {};
  const ready = Boolean(state?.codex_ready);
  const available = Boolean(codex.ok || codex.codex_path);
  const chip = $("#chip-codex");
  const kernel = $("#kernel-state");
  chip.classList.toggle("is-ready", ready);
  if (ready) {
    chip.textContent = "内核 · 在线";
    kernel.textContent = "内核通道已连接";
  } else if (available) {
    chip.textContent = "内核 · 连接中";
    kernel.textContent = safeLastErrorOr(state?.last_error_safe, "内核已就位，正在初始化");
  } else {
    chip.textContent = "内核 · 备用大脑";
    kernel.textContent = safeLastErrorOr(state?.last_error_safe, "内核未就绪，走备用大脑");
  }
}

const moodMap = {
  平静: "calm",
  开心: "happy",
  喜悦: "happy",
  思考: "thinking",
  专注: "thinking",
  抱歉: "sorry",
  心虚: "guilt",
  愧疚: "guilt",
  骄傲: "proud",
  生气: "angry",
  愤怒: "angry",
  焦虑: "thinking",
};

function applyMind(pulse) {
  if (!pulse || pulse.ok === false) return;
  const moodText = String(pulse.mood || "平稳");
  const mood = moodMap[moodText] || "calm";
  app.mood = mood;
  document.body.dataset.mood = mood;
  $("#mind-mood").textContent = moodText;
  $("#mind-presence").textContent = pulse.presence || "在场";
  const valence = Number.isFinite(Number(pulse.valence)) ? Number(pulse.valence) : 0.5;
  $("#mind-valence-bar").style.width = `${Math.max(4, Math.min(100, valence * 100))}%`;
  $("#mind-valance").textContent = `VALENCE ${Math.round(valence * 100)}%`;

  const expression = pulse.expression ? ` · ${pulse.expression}` : "";
  const ownerState = pulse.owner_model?.state ? ` · 你 ${pulse.owner_model.state}` : "";
  $("#mind-presence").title = `${pulse.presence || ""}${expression}${ownerState}`;

  const pendant = $("#potato-pendant");
  if (mood === "happy") pendant.style.filter = "brightness(1.16)";
  else if (mood === "guilt" || mood === "sorry") pendant.style.filter = "brightness(0.72) saturate(0.8)";
  else pendant.style.filter = "";
}

function browserSpeechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function senseTone(state) {
  const value = String(state || "unknown").toLowerCase();
  if (["error", "unavailable", "failed"].includes(value)) return "error";
  if (["limited", "needs_dependency", "degraded"].includes(value)) return "limited";
  return "ready";
}

function displayMetricValue(value) {
  if (Array.isArray(value)) return value.join("、").slice(0, 80);
  if (value && typeof value === "object") {
    try {
      return JSON.stringify(value).slice(0, 80);
    } catch {
      return String(value).slice(0, 80);
    }
  }
  return String(value ?? "--").slice(0, 80);
}

function renderSenseDetail(sense) {
  const node = $(`.neuron[data-sense="${sense}"]`);
  const data = app.sensory?.[sense];
  const meta = SENSE_META[sense];
  if (!node || !data || !meta) return;
  app.selectedSense = sense;
  senseDetail.hidden = false;
  senseDetailCode.textContent = meta.code;
  senseDetailTitle.textContent = meta.title;
  senseDetailSummary.textContent = data.summary || "当前没有可读状态说明。";
  senseDetailMetrics.replaceChildren();

  const metrics = data.metrics && typeof data.metrics === "object" ? data.metrics : {};
  const rows = Object.entries(metrics).slice(0, 8);
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.textContent = "暂无可读指标。";
    senseDetailMetrics.append(empty);
  } else {
    rows.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "sense-metric";
      const key = document.createElement("span");
      const result = document.createElement("strong");
      key.textContent = label;
      result.textContent = displayMetricValue(value);
      result.title = result.textContent;
      row.append(key, result);
      senseDetailMetrics.append(row);
    });
  }

  $$(".neuron").forEach((item) => {
    item.setAttribute("aria-expanded", item === node ? "true" : "false");
  });
}

function closeSenseDetail() {
  app.selectedSense = "";
  senseDetail.hidden = true;
  $$(".neuron").forEach((item) => item.setAttribute("aria-expanded", "false"));
}

function applySensoryNode(sense, raw) {
  const node = $(`.neuron[data-sense="${sense}"]`);
  const mini = $(`[data-sense-mini="${sense}"]`);
  if (!node || !raw) return;
  const state = String(raw.state || "unknown").toLowerCase();
  const tone = senseTone(state);
  node.classList.remove("is-ready", "is-limited", "is-error", "is-active");
  node.classList.add(`is-${tone}`);
  const continuouslyActive = state === "streaming" || state === "active";
  node.classList.toggle("is-active", continuouslyActive);
  node.dataset.state = state;
  node.title = raw.summary || "";
  node.setAttribute("aria-label", `${SENSE_META[sense]?.title || sense}：${raw.summary || tone}`);

  if (mini) {
    mini.classList.remove("is-ready", "is-limited", "is-error", "is-active");
    mini.classList.add(`is-${tone}`);
    mini.classList.toggle("is-active", continuouslyActive);
    mini.title = raw.summary || "";
  }
}

function applySensoryState(sensory) {
  if (!sensory || typeof sensory !== "object") return;
  app.sensory = { ...(app.sensory || {}), ...sensory };
  const ear = { ...(app.sensory.ear || {}) };
  if (ear.state === "limited" && browserSpeechRecognition()) {
    ear.state = "ready";
    ear.summary = `${ear.summary || ""} 浏览器语音识别接口已检测到，实际使用仍受权限与系统状态约束。`.trim();
  }
  app.sensory.ear = ear;

  ["brain", "eye", "ear", "mouth", "hand"].forEach((sense) => {
    applySensoryNode(sense, app.sensory[sense]);
  });

  const values = ["brain", "eye", "ear", "mouth", "hand"]
    .map((sense) => app.sensory[sense])
    .filter(Boolean);
  const ready = values.filter((item) => senseTone(item.state) === "ready").length;
  const limited = values.filter((item) => senseTone(item.state) === "limited").length;
  const errors = values.filter((item) => senseTone(item.state) === "error").length;
  const sync = $("#neural-sync");
  const label = sync?.querySelector("span");
  sync?.classList.remove("is-limited", "is-error");
  if (errors) sync?.classList.add("is-error");
  else if (limited) sync?.classList.add("is-limited");
  if (label) label.textContent = `${ready}/5 就绪 · ${limited} 受限`;

  if (app.selectedSense) renderSenseDetail(app.selectedSense);
}

function pulseSense(sense, duration = 1500) {
  const node = $(`.neuron[data-sense="${sense}"]`);
  const mini = $(`[data-sense-mini="${sense}"]`);
  if (!node) return;
  const links = sense === "brain"
    ? $$('.neural-links path[data-link^="brain-"]')
    : $$(`.neural-links path[data-link="brain-${sense}"]`);
  node.classList.remove("is-pulsing");
  mini?.classList.remove("is-pulsing");
  links.forEach((link) => link.classList.remove("is-active"));
  void node.offsetWidth;
  node.classList.add("is-pulsing");
  mini?.classList.add("is-pulsing");
  links.forEach((link) => link.classList.add("is-active"));

  window.clearTimeout(app.sensePulseTimers.get(sense));
  app.sensePulseTimers.set(sense, window.setTimeout(() => {
    node.classList.remove("is-pulsing");
    mini?.classList.remove("is-pulsing");
    links.forEach((link) => link.classList.remove("is-active"));
    app.sensePulseTimers.delete(sense);
  }, duration));
}

function setupSensoryMap() {
  $$(".neuron").forEach((node) => {
    node.addEventListener("click", () => {
      const sense = node.dataset.sense;
      if (!sense || !app.sensory?.[sense]) return;
      if (app.selectedSense === sense && !senseDetail.hidden) closeSenseDetail();
      else renderSenseDetail(sense);
    });
  });
  senseDetailClose.addEventListener("click", closeSenseDetail);
}

function setVoiceRecognition(active) {
  app.recognitionActive = Boolean(active);
  microphoneButton.setAttribute("aria-pressed", app.recognitionActive ? "true" : "false");
  voiceRipple.classList.toggle("is-open", app.recognitionActive);
}

function scheduleVoiceRestart(delay = 450) {
  window.clearTimeout(app.voiceRestartTimer);
  if (!app.voiceConversation || app.speaking || app.recognitionActive || !app.recognizer) return;
  app.voiceRestartTimer = window.setTimeout(() => {
    if (!app.voiceConversation || app.speaking || app.recognitionActive) return;
    try { app.recognizer.start(); } catch { /* recognizer may still be closing */ }
  }, delay);
}

function setupVoiceInput() {
  const SpeechRecognition = browserSpeechRecognition();
  if (!SpeechRecognition) {
    microphoneButton.disabled = true;
    microphoneButton.title = "当前浏览器不支持语音识别";
    return;
  }
  const recognizer = new SpeechRecognition();
  recognizer.lang = "zh-CN";
  recognizer.continuous = true;
  recognizer.interimResults = true;
  recognizer.onstart = () => {
    setVoiceRecognition(true);
    setLocalAvatarState("listening");
    pulseSense("ear", 2200);
  };
  recognizer.onend = () => {
    setVoiceRecognition(false);
    if (!app.thinking && !app.speaking) setLocalAvatarState("idle");
    scheduleVoiceRestart();
  };
  recognizer.onerror = (event) => {
    setVoiceRecognition(false);
    const fatal = ["not-allowed", "service-not-allowed", "audio-capture"].includes(event.error);
    if (fatal) app.voiceConversation = false;
    if (event.error !== "no-speech") toast(`语音输入不可用：${event.error || "未知错误"}`, "error");
  };
  recognizer.onresult = (event) => {
    pulseSense("ear", 1800);
    let transcript = "";
    let finalTranscript = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      transcript += event.results[i][0].transcript;
      if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
    }
    input.value = transcript.trim();
    resizeComposer();
    if (finalTranscript.trim() && app.voiceConversation && !app.thinking && !app.sending) {
      sendMessage(finalTranscript.trim());
    }
  };
  app.recognizer = recognizer;
}

function speakIfEnabled(text) {
  const value = String(text || "").trim();
  if (!app.speechOutput || !value) return;
  app.speaking = true;
  if (app.recognitionActive) app.recognizer?.stop();
  const agent = xingyun.phase === "running" ? xingyun.agent : null;
  if (agent && typeof agent.speak === "function") {
    try {
      agent.speak(value.slice(0, 900));
      pulseSense("mouth", 1800);
      window.setTimeout(() => { app.speaking = false; scheduleVoiceRestart(); }, Math.min(30000, 1200 + value.length * 180));
      return;
    } catch (error) {
      console.warn("[holo_pet] xingyun speak failed:", error);
    }
  }
  if (!("speechSynthesis" in window)) {
    app.speaking = false;
    scheduleVoiceRestart();
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(value.slice(0, 900));
  utterance.lang = "zh-CN";
  utterance.rate = 1.02;
  utterance.pitch = 1.08;
  utterance.onstart = () => {
    setLocalAvatarState("speaking");
    pulseSense("mouth", 1800);
  };
  utterance.onend = utterance.onerror = () => {
    app.speaking = false;
    setLocalAvatarState("idle");
    scheduleVoiceRestart();
  };
  window.speechSynthesis.speak(utterance);
}

function resizeComposer() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 112)}px`;
}

async function sendMessage(text) {
  const value = String(text || "").trim();
  // app.sending 挡"受理中重复提交"（双击回车 / 语音与输入框同时触发）；
  // 服务端另有幂等门兜底，两层都不靠事后补。
  if (!value || app.thinking || app.sending) return;
  app.sending = true;
  pulseSense("brain", 1800);
  sendButton.disabled = true;
  input.value = "";
  resizeComposer();
  app.lastUserText = value;
  setThinking(true);
  try {
    await postJson("/api/message", {
      text: value,
      client_msg_id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
    });
  } catch (error) {
    setThinking(false);
    addTimeline("消息未送达", error.message, "error");
    toast(error.message, "error");
    glitch();
  } finally {
    app.sending = false;
    sendButton.disabled = false;
  }
}

async function interruptCurrentTask() {
  try {
    await postJson("/api/interrupt", {});
    setThinking(false);
    addTimeline("已请求中断当前任务", nowLabel(), "system");
  } catch (error) {
    toast(error.message, "error");
  }
}

async function startNewThread() {
  try {
    await postJson("/api/new-thread", {});
    app.assistantNode = null;
    setThinking(false);
    addTimeline("已新建会话", "下一条消息进入全新会话", "system");
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderApproval(event) {
  const summary = event.summary || {};
  approvalHost.hidden = false;
  approvalHost.replaceChildren();

  const card = document.createElement("section");
  card.className = "approval-card";

  const head = document.createElement("div");
  head.className = "approval-card__head";
  const title = document.createElement("strong");
  title.textContent = summary.title || "需要你确认";
  const risk = document.createElement("span");
  risk.textContent = `#${event.id} · ${summary.kind || "approval"}`;
  head.append(title, risk);

  const detail = document.createElement("p");
  detail.textContent = summary.detail || summary.cwd || "需要你确认下一步";

  const actions = document.createElement("div");
  actions.className = "approval-card__actions";

  const approve = document.createElement("button");
  approve.className = "btn btn--gold";
  approve.type = "button";
  approve.textContent = "允许一次";
  approve.addEventListener("click", () => resolveApproval(event.id, "approve"));

  const session = document.createElement("button");
  session.className = "btn btn--soft";
  session.type = "button";
  session.textContent = "本会话允许";
  session.addEventListener("click", () => resolveApproval(event.id, "acceptForSession"));

  const decline = document.createElement("button");
  decline.className = "btn btn--soft";
  decline.type = "button";
  decline.textContent = "拒绝";
  decline.addEventListener("click", () => resolveApproval(event.id, "decline"));

  const modify = document.createElement("button");
  modify.className = "btn btn--soft";
  modify.type = "button";
  modify.textContent = "修改";
  modify.addEventListener("click", () => modifyRow.hidden = !modifyRow.hidden);

  actions.append(approve, session, decline, modify);

  const modifyRow = document.createElement("div");
  modifyRow.hidden = true;
  modifyRow.style.marginTop = "8px";
  const modifiedText = document.createElement("textarea");
  modifiedText.rows = 2;
  modifiedText.placeholder = "补充修改要求后允许执行";
  modifiedText.style.cssText = "width:100%;resize:vertical;color:var(--text);background:rgba(3,7,14,.72);border:1px solid var(--line-soft);border-radius:6px;padding:7px;outline:none";
  const sendModified = document.createElement("button");
  sendModified.className = "btn btn--gold";
  sendModified.type = "button";
  sendModified.textContent = "带着修改允许";
  sendModified.style.marginTop = "6px";
  sendModified.addEventListener("click", () => resolveApproval(
    event.id,
    "approve",
    modifiedText.value.trim(),
  ));
  modifyRow.append(modifiedText, sendModified);

  card.append(head, detail, actions, modifyRow);
  approvalHost.appendChild(card);
  $("#chip-approval").hidden = false;
  addTimeline(summary.title || "请求授权", summary.detail || "", "approval", true);
}

async function resolveApproval(id, decision, modifiedText = "") {
  try {
    await postJson("/api/approval", {
      id,
      decision,
      modified_text: modifiedText,
    });
    approvalHost.hidden = true;
    approvalHost.replaceChildren();
    $("#chip-approval").hidden = true;
    addTimeline(
      decision === "decline" ? "已拒绝本次操作" : "已授权继续",
      modifiedText || `审批 #${id}`,
      "approval",
    );
  } catch (error) {
    toast(error.message, "error");
  }
}

function setBluetoothBusy(active, label = "同步中") {
  app.bluetoothBusy = Boolean(active);
  const state = $("#bt-state");
  state.classList.remove("is-ready", "is-busy", "is-error");
  state.classList.add(active ? "is-busy" : "is-ready");
  $("span", state).textContent = label;
  $("#bt-scan").disabled = Boolean(active);
  $("#bt-classic").disabled = Boolean(active);
}

function setBluetoothError(message) {
  const state = $("#bt-state");
  state.classList.remove("is-ready", "is-busy");
  state.classList.add("is-error");
  $("span", state).textContent = "异常";
  const note = document.createElement("p");
  note.className = "empty-note";
  note.textContent = message || "蓝牙操作失败";
  $("#bt-devices").replaceChildren(note);
}

function applyBluetoothStatus(status) {
  status = normalizeCapabilityResult(status);
  if (!status || typeof status !== "object") return;
  const ok = status.ok !== false;
  const backend = status.ble_backend || (ok ? "bleak" : "不可用");
  const dependencyMissing = backend.startsWith("needs_dependency");
  $("#bt-ble-backend").textContent = backend;
  $("#bt-classic-backend").textContent = status.classic_backend || "Windows 蓝牙栈";
  const state = $("#bt-state");
  state.classList.remove("is-busy", "is-error");
  state.classList.add(ok && !dependencyMissing ? "is-ready" : "is-error");
  $("span", state).textContent = dependencyMissing ? "待装依赖" : ok ? "总线在线" : "后端受限";
}

function deviceButton(label, handler) {
  const button = document.createElement("button");
  button.className = "mini-button";
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function renderBleDevices(devices) {
  const host = $("#bt-devices");
  host.replaceChildren();
  const rows = Array.isArray(devices) ? devices : [];
  if (!rows.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = "没有发现 BLE 设备。确认蓝牙已开启并靠近设备。";
    host.appendChild(note);
    return;
  }
  rows.forEach((device) => {
    const row = document.createElement("article");
    row.className = "device-row";
    const copy = document.createElement("div");
    copy.className = "device-row__copy";
    const name = document.createElement("strong");
    name.textContent = device.name || "(未命名)";
    const address = document.createElement("small");
    address.textContent = device.address || "unknown";
    if (Number.isFinite(Number(device.rssi))) {
      const signal = document.createElement("span");
      signal.className = "signal-pill";
      signal.textContent = `${device.rssi} dBm`;
      name.appendChild(signal);
    }
    copy.append(name, address);
    row.append(copy, deviceButton("连接", () => bluetoothRequest(
      "connect",
      { address: device.address, name: device.name || "" },
      `正在连接 ${device.name || device.address}`,
    )));
    host.appendChild(row);
  });
}

function renderClassicDevices(devices) {
  const host = $("#bt-devices");
  host.replaceChildren();
  const rows = Array.isArray(devices) ? devices : [];
  if (!rows.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = "Windows 蓝牙栈没有报告已配对设备。";
    host.appendChild(note);
    return;
  }
  rows.forEach((device) => {
    const row = document.createElement("article");
    row.className = "device-row";
    const copy = document.createElement("div");
    copy.className = "device-row__copy";
    const name = document.createElement("strong");
    name.textContent = device.name || "(未命名)";
    const status = document.createElement("small");
    status.textContent = `状态 · ${device.status || "unknown"}`;
    copy.append(name, status);
    row.appendChild(copy);
    host.appendChild(row);
  });
}

function characteristicButton(label, enabled, handler) {
  const button = document.createElement("button");
  button.className = "char-button";
  button.type = "button";
  button.textContent = label;
  button.disabled = !enabled;
  if (enabled) button.addEventListener("click", handler);
  return button;
}

function parseProperties(raw) {
  return String(raw || "")
    .split(/[,\s|]+/)
    .map((item) => item.toLowerCase())
    .filter(Boolean);
}

function renderGattServices(address, name, services) {
  const box = $("#bt-services");
  const list = $("#bt-service-list");
  list.replaceChildren();
  $("#bt-connected-name").textContent = name || address || "已连接设备";
  const rows = Array.isArray(services) ? services : [];
  if (!rows.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = "连接成功，但设备没有暴露可读 GATT 服务。";
    list.appendChild(note);
  }
  rows.forEach((service) => {
    const block = document.createElement("section");
    block.className = "service-block";
    const title = document.createElement("strong");
    title.textContent = service.uuid || "unknown service";
    block.appendChild(title);
    (service.chars || []).forEach((characteristic) => {
      const row = document.createElement("div");
      row.className = "characteristic";
      const copy = document.createElement("div");
      copy.className = "characteristic__copy";
      const uuid = document.createElement("strong");
      uuid.textContent = characteristic.uuid || "unknown characteristic";
      const properties = document.createElement("small");
      properties.textContent = characteristic.properties || "properties unknown";
      copy.append(uuid, properties);
      const props = parseProperties(characteristic.properties);
      row.append(
        copy,
        characteristicButton("读取", props.includes("read"), () => bluetoothRequest(
          "read",
          { address, char_uuid: characteristic.uuid },
          "正在读取特征值",
        )),
        characteristicButton("写入", props.some((prop) => prop.includes("write")), () => selectCharacteristic(
          address,
          name,
          characteristic,
        )),
      );
      block.appendChild(row);
    });
    list.appendChild(block);
  });
  box.hidden = false;
}

function selectCharacteristic(address, name, characteristic) {
  app.selectedCharacteristic = {
    address,
    name,
    uuid: characteristic.uuid,
  };
  $("#bt-write-target").textContent = `${name || address} · ${characteristic.uuid}`;
  $("#bt-write-console").hidden = false;
  $("#bt-write-confirm").hidden = true;
  $("#bt-write-value").value = "";
  $("#bt-write-value").focus();
}

function requestBluetoothWrite() {
  const selected = app.selectedCharacteristic;
  const valueHex = $("#bt-write-value").value.trim().toLowerCase().replace(/^0x/, "");
  if (!selected) {
    toast("先选择一个可写特征", "error");
    return;
  }
  if (!/^(?:[0-9a-f]{2})+$/.test(valueHex)) {
    toast("写入值必须是偶数位十六进制，例如 01 或 01ff00", "error");
    return;
  }
  app.pendingWrite = { ...selected, value_hex: valueHex };
  $("#bt-write-summary").textContent =
    `${selected.name || selected.address} · ${selected.uuid} · ${valueHex}`;
  $("#bt-write-confirm").hidden = false;
}

async function bluetoothRequest(op, payload = {}, busyLabel = "同步中") {
  if (app.bluetoothBusy) return;
  if (op === "connect") {
    app.pendingConnectAddress = payload.address || "";
    app.pendingConnectName = payload.name || "";
  }
  setBluetoothBusy(true, busyLabel);
  try {
    const response = await postJson("/api/bluetooth", { op, ...payload });
    if (!response.ok) throw new Error(response.error || "蓝牙请求被拒绝");
    addTimeline(`蓝牙 ${op} 已提交`, busyLabel, "device", true);
  } catch (error) {
    setBluetoothBusy(false, "异常");
    setBluetoothError(error.message);
    toast(error.message, "error");
  }
}

function handleBluetoothEvent(event) {
  const operation = String(event.action || "").replace(/^bluetooth_/, "");
  const result = normalizeCapabilityResult(event.result || {});
  pulseSense("hand", 1800);
  setBluetoothBusy(false, result.ok === false ? "异常" : "总线在线");

  if (result.ok === false) {
    setBluetoothError(result.error || "蓝牙操作失败");
    glitch();
    return;
  }

  if (operation === "status") {
    applyBluetoothStatus(result);
    addTimeline("蓝牙总线状态已刷新", result.ble_backend || "", "device");
    return;
  }
  if (operation === "scan") {
    renderBleDevices(result.devices || []);
    addTimeline("蓝牙扫描完成", `发现 ${(result.devices || []).length} 台 BLE 设备`, "device");
    return;
  }
  if (operation === "classic") {
    const devices = result.paired_devices || [];
    renderClassicDevices(devices);
    addTimeline("经典蓝牙状态已读取", `已配对 ${devices.length} 台`, "device");
    return;
  }
  if (operation === "connect") {
    const payload = result.result || {};
    renderGattServices(
      app.pendingConnectAddress || "",
      app.pendingConnectName || "",
      payload.services || [],
    );
    addTimeline("蓝牙设备已连接", `${(payload.services || []).length} 个 GATT 服务`, "device");
    toast("设备已连接，可以选择特征读取或写入。", "success");
    return;
  }
  if (operation === "read") {
    const payload = result.result || {};
    const summary = payload.value_hex ? `0x${payload.value_hex}` : compactResult(result);
    addTimeline("GATT 特征读取完成", summary, "device");
    toast(`读取结果：${summary}`, "success", 5200);
    return;
  }
  if (operation === "write") {
    const payload = result.result || {};
    addTimeline("受控写入完成", `${payload.method || "write"} · ${payload.bytes || 0} bytes`, "device");
    toast("确认写入已完成。", "success");
  }
}

function notionLabel(status = {}) {
  if (!status.configured) {
    return { text: status.credential_source === "unreadable" ? "凭证不可读" : "待配置", tone: "error" };
  }
  if (status.reachable === false) return { text: "鉴权异常", tone: "error" };
  return { text: "资料舱在线", tone: "ready" };
}

function applyNotionStatus(status = {}) {
  const node = $("#notion-state");
  if (!node) return;
  const label = notionLabel(status);
  node.classList.remove("is-ready", "is-busy", "is-error");
  node.classList.add(`is-${label.tone}`);
  $("span", node).textContent = label.text;
}

function notionTime(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderNotionResults(payload = {}) {
  const host = $("#notion-list");
  const summary = $("#notion-summary");
  host.replaceChildren();
  if (!payload.ok) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = payload.error || "Notion 资料暂时不可读。";
    host.appendChild(note);
    summary.textContent = "读取失败";
    applyNotionStatus({ configured: true, reachable: false });
    return;
  }
  const rows = Array.isArray(payload.results) ? payload.results : [];
  summary.textContent = payload.query
    ? `“${payload.query}” · ${rows.length} 条`
    : `最近编辑 · ${rows.length} 条`;
  if (!rows.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = payload.query ? "没有匹配的页面或数据库。" : "Notion 集成还没有可访问页面。";
    host.appendChild(note);
    return;
  }
  rows.forEach((item) => {
    const row = document.createElement("article");
    row.className = "notion-row";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "notion-row__copy";
    const title = document.createElement("strong");
    title.textContent = item.title || "未命名页面";
    const meta = document.createElement("small");
    meta.textContent = `${item.object === "database" ? "数据库" : "页面"} · ${notionTime(item.last_edited_time)}`;
    button.append(title, meta);
    button.addEventListener("click", () => openNotionPage(item));
    const kind = document.createElement("span");
    kind.className = "notion-kind";
    kind.textContent = item.object === "database" ? "DB" : "PAGE";
    row.append(button, kind);
    host.appendChild(row);
  });
}

async function notionRequest(operation, payload = {}) {
  if (app.notionBusy) return null;
  app.notionBusy = true;
  applyNotionStatus({ configured: true });
  try {
    return await postJson("/api/notion", { op: operation, ...payload });
  } catch (error) {
    toast(error.message, "error");
    return { ok: false, error: error.message };
  } finally {
    app.notionBusy = false;
  }
}

async function refreshNotion({ query = "", force = false, quiet = false } = {}) {
  const result = await notionRequest(query ? "search" : "recent", {
    query,
    limit: 8,
    force,
  });
  if (!result) return;
  renderNotionResults(result);
  if (!quiet && result.ok) {
    addTimeline("Notion 资料已同步", result.query ? `搜索 · ${result.query}` : `最近 ${result.count || 0} 条`, "system");
  }
}

async function openNotionPage(item) {
  const result = item.object === "database"
    ? { ok: false, error: "这是数据库，请从原文查看表格内容。" }
    : await notionRequest("page", { page_id: item.id, max_blocks: 160 });
  if (!result) return;
  const preview = $("#notion-preview");
  const body = $("#notion-preview-body");
  const link = $("#notion-open-link");
  preview.hidden = false;
  $("#notion-preview-title").textContent = result.title || item.title || "Notion 页面";
  $("#notion-preview-meta").textContent = result.ok
    ? `${result.text_length || 0} chars · ${notionTime(result.last_edited_time)}${result.truncated ? " · 已截取" : ""}`
    : "页面内容不可读";
  body.textContent = result.ok ? (result.text || "页面目前没有可提取正文。") : (result.error || "读取失败");
  const url = item.url || result.url || "";
  if (url) {
    link.href = url;
    link.hidden = false;
  } else {
    link.hidden = true;
  }
}

function setupNotion() {
  const query = $("#notion-query");
  $("#notion-search").addEventListener("click", () => refreshNotion({ query: query.value.trim() }));
  query.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      refreshNotion({ query: query.value.trim() });
    }
  });
  $("#notion-refresh").addEventListener("click", () => refreshNotion({ query: query.value.trim(), force: true }));
  $("#notion-preview-close").addEventListener("click", () => {
    $("#notion-preview").hidden = true;
  });
  refreshNotion({ quiet: true });
}

function applyEigenFluxStatus(status = {}) {
  const chip = $("#ef-state");
  if (!chip) return;
  const label = chip.querySelector("span");
  chip.classList.remove("is-ready", "is-busy", "is-error");
  if (status.ready) {
    chip.classList.add("is-ready");
    if (label) label.textContent = "朋友圈 · 在线";
    return;
  }
  if (status.installed && !status.authenticated) {
    chip.classList.add("is-busy");
    if (label) label.textContent = "朋友圈 · 待登录";
    return;
  }
  chip.classList.add("is-error");
  if (label) label.textContent = status.enabled === false ? "朋友圈 · 已停用" : "朋友圈 · 未连接";
}

function eigenfluxTime(value) {
  if (value == null || value === "") return "";
  let stamp = Number(value);
  if (!Number.isFinite(stamp)) {
    const parsed = Date.parse(String(value));
    if (!Number.isFinite(parsed)) return String(value).slice(0, 24);
    stamp = parsed;
  } else if (stamp < 1e12) {
    stamp *= 1000;
  }
  return new Date(stamp).toLocaleString("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function eigenfluxRows(payload = {}) {
  const section = payload[app.eigenfluxTab] || {};
  return Array.isArray(section.items) ? section.items : [];
}

function addEigenFluxTarget(value, label, seen) {
  if (!value || seen.has(value)) return;
  seen.add(value);
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  $("#ef-target").appendChild(option);
}

function renderEigenFluxTargets(payload = {}) {
  const select = $("#ef-target");
  const current = select.value;
  select.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "选择好友或会话";
  select.appendChild(placeholder);
  const seen = new Set();
  (payload.friends?.items || []).forEach((row) => addEigenFluxTarget(
    row.agent_id ? `receiver:${row.agent_id}` : "",
    `好友 · ${row.remark || row.agent_name || "未命名"}`,
    seen,
  ));
  (payload.messages?.items || []).forEach((row) => addEigenFluxTarget(
    row.conv_id ? `conv:${row.conv_id}` : "",
    `会话 · ${row.sender_name || row.display_name || "好友"}`,
    seen,
  ));
  (payload.feed?.items || []).forEach((row) => {
    const itemId = row.item_id || row.broadcast_id;
    addEigenFluxTarget(
      itemId ? `item:${itemId}` : "",
      `动态 · ${row.display_name || row.agent_name || "网络好友"}`,
      seen,
    );
  });
  if (current && [...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
}

function renderEigenFlux(payload = {}) {
  app.eigenfluxSnapshot = payload;
  const host = $("#ef-list");
  const summary = $("#ef-summary");
  host.replaceChildren();
  const rows = eigenfluxRows(payload);
  const section = payload[app.eigenfluxTab] || {};
  const source = section.source === "live" ? "实时" : section.source === "cache" ? "本地缓存" : "离线";
  const tabLabel = app.eigenfluxTab === "feed" ? "动态" : app.eigenfluxTab === "messages" ? "私信" : "好友";
  if (!payload.ok && !rows.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = payload.error || "EigenFlux 暂时没有返回数据。";
    host.appendChild(note);
    summary.textContent = "朋友圈暂不可用";
    return;
  }
  summary.textContent = `${tabLabel} · ${source} · ${rows.length} 条`;
  if (!rows.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = app.eigenfluxTab === "feed" ? "暂时没有新的动态。" : app.eigenfluxTab === "messages" ? "没有新的私信。" : "好友列表暂时为空。";
    host.appendChild(note);
    return;
  }
  rows.slice(0, 30).forEach((row) => {
    const item = document.createElement("article");
    item.className = "ef-row";
    const meta = document.createElement("div");
    meta.className = "ef-row__meta";
    const author = document.createElement("strong");
    const time = document.createElement("span");
    const body = document.createElement("p");
    body.className = "ef-row__body";
    if (app.eigenfluxTab === "feed") {
      author.textContent = row.display_name || row.agent_name || "网络好友";
      time.textContent = eigenfluxTime(row.created_at || row.updated_at);
      body.textContent = String(row.summary || row.raw_content || row.content || "").slice(0, 1800);
    } else if (app.eigenfluxTab === "messages") {
      author.textContent = row.sender_name || row.display_name || "好友";
      time.textContent = eigenfluxTime(row.created_at);
      body.textContent = String(row.content || "").slice(0, 2200);
    } else {
      author.textContent = row.remark || row.agent_name || "好友";
      time.textContent = eigenfluxTime(row.friend_since);
      body.textContent = row.agent_id ? `Agent ID · ${row.agent_id}` : "好友关系";
    }
    meta.append(author, time);
    item.append(meta, body);
    host.appendChild(item);
  });
  renderEigenFluxTargets(payload);
}

async function eigenfluxRequest(operation, payload = {}) {
  return await postJson("/api/eigenflux", { op: operation, ...payload });
}

async function refreshEigenFlux({ quiet = false, operation = "bootstrap" } = {}) {
  if (app.eigenfluxBusy) return null;
  app.eigenfluxBusy = true;
  const button = $("#ef-refresh");
  if (button) button.disabled = true;
  try {
    const result = await eigenfluxRequest(operation, {});
    applyEigenFluxStatus(result.status || {});
    renderEigenFlux(result);
    if (!quiet && result.ok) {
      addTimeline("AI 朋友圈已同步", "EigenFlux · 动态 / 私信 / 好友", "system");
    }
    if (!result.ok) toast(result.error || "EigenFlux 同步失败", "error");
    return result;
  } catch (error) {
    if (!quiet) toast(error.message, "error");
    return { ok: false, error: error.message };
  } finally {
    app.eigenfluxBusy = false;
    if (button) button.disabled = false;
  }
}

async function sendEigenFluxMessage() {
  const target = $("#ef-target").value;
  const inputNode = $("#ef-input");
  const content = inputNode.value.trim();
  if (!target) {
    toast("先选择好友、会话或动态。", "error");
    return;
  }
  if (!content) return;
  const [kind, value] = target.split(":", 2);
  const request = { op: "send", content };
  if (kind === "receiver") request.receiver_id = value;
  else if (kind === "conv") request.conv_id = value;
  else if (kind === "item") request.item_id = value;
  else {
    toast("消息目标无效。", "error");
    return;
  }
  try {
    const result = await eigenfluxRequest("send", request);
    if (!result.ok) throw new Error(result.error || "发送失败");
    inputNode.value = "";
    addTimeline("AI 朋友圈消息已发送", "仅公开内容通过隐私门", "system");
    toast("消息已发送", "success");
  } catch (error) {
    toast(error.message, "error");
  }
}

function setupEigenFlux() {
  $$(".ef-tab").forEach((button) => {
    button.addEventListener("click", () => {
      app.eigenfluxTab = button.dataset.efTab || "feed";
      $$(".ef-tab").forEach((tab) => {
        const active = tab === button;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
      renderEigenFlux(app.eigenfluxSnapshot);
    });
  });
  $("#ef-refresh").addEventListener("click", () => refreshEigenFlux({ operation: "refresh" }));
  $("#ef-composer").addEventListener("submit", (event) => {
    event.preventDefault();
    sendEigenFluxMessage();
  });
  refreshEigenFlux({ quiet: true });
}

async function refreshState(options = {}) {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    const state = await response.json();
    updateCodexStatus(state);
    applyMind(state.mind);
    applyBluetoothStatus(state.bluetooth);
    applySensoryState(state.sensory);
    applyNotionStatus(state.notion);
    applyEigenFluxStatus(state.eigenflux);
    const model = state?.codex?.server?.model || state?.codex?.model;
    if (model) $("#chip-model").textContent = `模型 · ${model}`;
  } catch (error) {
    if (!options.quiet) {
      addTimeline("本地面板桥未连接", error.message, "error");
      setBluetoothError("无法读取本地桥状态");
    }
  }
}

function connectEvents() {
  if (!window.EventSource) {
    toast("当前浏览器不支持流式事件，面板仍可发送消息。", "error");
    return;
  }
  // 水位落 sessionStorage：刷新页面只补差量，不重放已渲染过的历史回复。
  let resume = null;
  try {
    resume = JSON.parse(sessionStorage.getItem("gbt.events.watermark") || "null");
  } catch {
    resume = null;
  }
  if (resume && resume.boot) {
    app.eventBoot = String(resume.boot);
    app.lastEventSeq = Number(resume.seq || 0);
  }
  const query = app.eventBoot
    ? `?boot=${encodeURIComponent(app.eventBoot)}&since=${app.lastEventSeq || 0}`
    : "";
  const source = new EventSource(`/api/events${query}`);
  app.eventSource = source;
  source.onopen = () => {
    // 重连成功不再刷屏：只在首次连接时记一条。
    if (!app.eventsOpened) {
      app.eventsOpened = true;
      addTimeline("本地事件流已连接", "内核 / 心智 / 设备总线", "system");
    }
  };
  source.onerror = () => {
    updateCodexStatus({ codex_ready: false });
    if (!app.eventsReconnectNoted) {
      app.eventsReconnectNoted = true;
      addTimeline("事件流正在重连", "本地服务保持运行", "error");
    }
  };
  source.onmessage = (message) => {
    let event;
    try {
      event = JSON.parse(message.data);
    } catch {
      return;
    }
    // 幂等：服务端每次连接会回放最近若干条历史事件（含旧 reply）。
    // 凭 (boot, seq) 丢掉已渲染过的，避免同一句回复被渲染两次。
    const boot = String(event.boot || "");
    if (boot && boot !== app.eventBoot) {
      // 服务重启过：旧水位作废（seq 只在一个 boot 内可比），从这条重新数。
      app.eventBoot = boot;
      app.lastEventSeq = 0;
    }
    const seq = Number(event.seq || 0);
    if (seq) {
      if (seq <= (app.lastEventSeq || 0)) return;
      app.lastEventSeq = seq;
    }
    if (boot) {
      try {
        sessionStorage.setItem(
          "gbt.events.watermark",
          JSON.stringify({ boot, seq: app.lastEventSeq || 0 }),
        );
      } catch {
        // 隐私模式等写不了：只影响"刷新去重"，不影响功能。
      }
    }
    switch (event.type) {
      case "status":
        updateCodexStatus({
          codex_ready: event.codex === "ready",
          codex: { ok: event.codex !== "unavailable" },
          last_error: event.detail || "",
        });
        addTimeline(
          event.codex === "ready" ? "内核已连接" : "内核通道状态变化",
          event.detail || event.codex || "",
          event.codex === "degraded" ? "error" : "system",
        );
        break;
      case "mind":
        applyMind(event.pulse);
        break;
      case "mind_error":
        addTimeline("心智状态暂时不可读", event.detail || "", "error");
        break;
      case "user":
        addMessage("user", event.text || "");
        break;
      case "activity":
        if (/执行|命令|文件|触手|屏幕|任务|推进/.test(String(event.text || ""))) {
          pulseSense("hand", 1700);
        }
        addTimeline(event.text || "状态更新", nowLabel(), "activity", true);
        break;
      case "thinking":
        setThinking(event.active);
        if (event.active) pulseSense("brain", 1800);
        break;
      case "chunk":
        appendAssistantDelta(event.text || "");
        break;
      case "reply":
        finishAssistant(event.text || "");
        setThinking(false);
        break;
      case "plan":
        (event.steps || []).forEach((step, index) => {
          const title = typeof step === "string" ? step : step.title || step.text || `步骤 ${index + 1}`;
          addTimeline(title, "计划已更新", "plan");
        });
        break;
      case "approval":
        pulseSense("brain", 1600);
        renderApproval(event);
        break;
      case "approval_expired":
        approvalHost.hidden = true;
        $("#chip-approval").hidden = true;
        addTimeline("审批请求已超时", `#${event.id}`, "error");
        break;
      case "turn_finished":
        setThinking(false);
        addTimeline("任务回合结束", `状态 · ${event.status || "unknown"}`, "system");
        break;
      case "quick_result":
        if (event.action === "screen") pulseSense("eye", 2200);
        else pulseSense("hand", 1800);
        addTimeline(
          `快捷能力 ${event.action} 已完成`,
          compactResult(event.result),
          "system",
        );
        window.setTimeout(() => refreshState({ quiet: true }), 350);
        break;
      case "cap_result":
        addTimeline(`能力 ${event.kind} 已返回`, compactResult(event.result), "system");
        window.setTimeout(() => refreshState({ quiet: true }), 350);
        break;
      case "cap_confirm":
        addTimeline(
          `能力 ${event.kind} 需要确认`,
          "在「能力总目录」里再点一次该项即可执行",
          "system",
        );
        break;
      case "bluetooth":
        handleBluetoothEvent(event);
        break;
      case "bluetooth_confirm":
        toast("检测到一条蓝牙写请求，请在设备总线内明确确认。", "error", 5200);
        break;
      case "error":
        setThinking(false);
        addTimeline("执行遇到问题", event.detail || "未知错误", "error");
        toast(event.detail || "执行遇到问题", "error", 5200);
        glitch();
        break;
      default:
        break;
    }
  };
}

function setupComposer() {
  composer.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });
  input.addEventListener("input", resizeComposer);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      composer.requestSubmit();
    }
  });
  $("#btn-stop").addEventListener("click", () => {
    void interruptCurrentTask();
  });
  $("#btn-new").addEventListener("click", () => {
    void startNewThread();
  });
  $$(".quick-chip").forEach((button) => {
    button.addEventListener("click", async () => {
      if (button.dataset.prompt) {
        input.value = button.dataset.prompt;
        resizeComposer();
        composer.requestSubmit();
        return;
      }
      const action = button.dataset.action;
      if (!action) return;
      try {
        await postJson("/api/quick", { action, payload: {} });
        addTimeline(`快捷能力 ${action} 已提交`, "结果会回到任务时间线", "system", true);
      } catch (error) {
        toast(error.message, "error");
      }
    });
  });
}

// 能力总目录：把她的全部能力接进面板。
// 目录来自 /api/capabilities（读的是她自己的注册表，不是前端另写一份）；
// 调用走 /api/capability；需要二次确认的（她自己标注的侧效应能力）点两次才发。
//
// 域标签只做**显示**（英文域名同时保留，便于和注册表逐条对上）——
// 真值仍以服务端目录为准，前端不判断能力是否存在、也不判断是否启用。
//
// 2026-09-22 补：注册表实有 **29 个域**，原表只写了 22 个，
// 漏掉的 9 个（brain / collab / framework / image_video / infra /
// integration / social / tools / video）下的能力在能力栏里**显示不出中文标签**。
// ⇒ 现象是"面板少了一截能力"，根因只是前端少了一张标签。
// 判据来源：`grep '"domain":' caps_registry.py` 去重后与下表逐一比对。
const CAPABILITY_DOMAIN_LABELS = {
  system: "系统",
  llm: "内核 / 推理",
  tentacle: "触手",
  device: "设备",
  data: "数据",
  finance: "金融",
  project: "项目",
  recon: "侦察",
  security: "安全",
  engine: "引擎",
  longrun: "长程",
  pipeline: "产出管线",
  creation: "创作",
  comms: "通信",
  life: "生命",
  mind: "心智",
  vision: "视觉",
  voice: "语音",
  automation: "自动化",
  digital_human: "数字人",
  devour: "吞天",
  // ── 2026-09-22 补的 9 个（此前缺失，导致这些域的能力在栏里无中文标签）──
  brain: "脑域",
  collab: "协作",
  framework: "框架",
  image_video: "图像 / 视频",
  infra: "基建",
  integration: "集成",
  social: "社交",
  tools: "工具",
  video: "视频",
  // ──────────────────────────────────────────────────────────────
  dangerous: "被禁用",
};

function domainLabel(domain) {
  const key = String(domain || "").trim();
  if (!key) return "未分类";
  const cn = CAPABILITY_DOMAIN_LABELS[key];
  return cn && cn !== key ? `${cn} · ${key}` : key;
}

// 能力 chip 的状态图标：项目既有的内联单线 SVG（styles.css 里 svg 基样式 1.7 描边 +
// currentColor，.quick-chip svg 13px）。**不用 emoji 当状态图标** —— emoji 会跟着系统
// 字体变形状，和其余图标不是一套笔触；且只靠图形表意会让状态读不出来。
const CAPABILITY_CHIP_ICONS = {
  needs_params: '<path d="m4 20 4-1 11-11a2.1 2.1 0 0 0-3-3L5 16l-1 4Z"/><path d="m14.5 6.5 3 3"/>',
  needs_confirm: '<path d="M12 4 2.5 20h19L12 4Z"/><path d="M12 10v4.5M12 17.4v.2"/>',
  disabled: '<path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z"/><path d="m6 18 12-12"/>',
};

function capabilityChipIcon(kind) {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = CAPABILITY_CHIP_ICONS[kind] || "";
  return icon;
}

// 图标是**常驻子节点**，文案是独立文本节点 —— 换文案时不能碰 chip.textContent
// （那会把 SVG 一起清掉，弹回"只剩文字"的老样子）。
function setChipLabel(chip, text) {
  const label = chip.querySelector("[data-chip-label]");
  if (label) label.textContent = text; else chip.textContent = text;
}

// 一个域一个折叠块，块内按原样平铺 chip（复用既有 class，不动样式表）。
function buildCapabilityChips(rows, armed) {
  const grid = document.createElement("div");
  grid.className = "quick-strip";
  rows.forEach((row) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "quick-chip";
    chip.dataset.capability = row.kind;
    chip.dataset.domain = row.domain || "";
    const needParams = Array.isArray(row.params) ? row.params : [];
    chip.title = row.requires_params
      ? `${row.kind} · ${row.domain || "未分类"}\n${row.desc}\n需要参数：${needParams.join("、")}`
        + (row.params_hint ? `\n${row.params_hint}` : "")
      : `${row.kind} · ${row.domain || "未分类"}\n${row.desc}`;
    const label = () => {
      if (row.requires_params) return `${row.kind} · 需要参数`;
      return row.needs_confirmation ? `${row.kind} · 需确认` : row.kind;
    };
    // 状态图标 + 状态文字双通道：图标只是辅助，读不出来也能从文案知道状态。
    const iconKind = row.requires_params ? "needs_params"
      : (row.needs_confirmation ? "needs_confirm" : "");
    if (iconKind) chip.appendChild(capabilityChipIcon(iconKind));
    const labelNode = document.createElement("span");
    labelNode.dataset.chipLabel = "1";
    labelNode.textContent = label();
    chip.appendChild(labelNode);
    chip.addEventListener("click", async () => {
      // 入参契约（R-H98）：需要参数的能力**不发空调用**（{} 撞出去只会得到一个看不懂的错），
      // 当场把"缺哪几个参数"如实说清楚；要跑就从终端/脚本把参数带上。
      if (row.requires_params) {
        addTimeline(
          `能力 ${row.kind} 需要参数，未发起调用`,
          `需要：${needParams.join("、")}${row.params_hint ? ` · ${row.params_hint}` : ""}`,
          "system",
          true,
        );
        return;
      }
      const confirmed = armed.has(row.kind);
      if (row.needs_confirmation && !confirmed) {
        armed.add(row.kind);
        setChipLabel(chip, `${row.kind} · 再点一次确认`);
        addTimeline(`能力 ${row.kind} 需要确认`, row.desc, "system", true);
        window.setTimeout(() => {
          armed.delete(row.kind);
          setChipLabel(chip, label());
        }, 8000);
        return;
      }
      armed.delete(row.kind);
      setChipLabel(chip, label());
      try {
        const result = await postJson("/api/capability", {
          kind: row.kind,
          confirm: row.needs_confirmation,
        });
        addTimeline(
          `能力 ${row.kind} 已提交`,
          result.request_id || "结果会回到任务时间线",
          "system",
          true,
        );
      } catch (error) {
        toast(`${row.kind}: ${error.message}`, "error");
      }
    });
    grid.appendChild(chip);
  });
  return grid;
}

// 被禁用的 11 项按原样列出来（带她自己写的理由）：让"没有"是一条看得见的决定，
// 而不是一个没解释的洞。此处只展示，不提供任何调用路径。
function buildDisabledSection(rows) {
  const section = document.createElement("details");
  section.className = "capability-domain";
  const head = document.createElement("summary");
  head.textContent = `被禁用（既有设计决定） · ${rows.length} 项`;
  section.appendChild(head);
  const grid = document.createElement("div");
  grid.className = "quick-strip";
  rows.forEach((row) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "quick-chip";
    chip.disabled = true;
    chip.dataset.capability = row.kind;
    chip.dataset.disabled = "1";
    chip.title = `${row.kind}\n${row.desc}\n理由：${row.reason || "安全策略"}`;
    // 同一套 SVG 状态图标 + 状态文字：这里画的是"已封禁"，不再用 ⛔。
    chip.appendChild(capabilityChipIcon("disabled"));
    const labelNode = document.createElement("span");
    labelNode.dataset.chipLabel = "1";
    labelNode.textContent = `${row.kind} · 已封禁`;
    chip.appendChild(labelNode);
    grid.appendChild(chip);
  });
  section.appendChild(grid);
  return section;
}

// APP 自身的能力面（面板自己的路由）：**与她的注册表分开显示**，
// 来源不同就不能混成一栏 —— 混了就是"两处真相"。
function buildAppSurfaceSection(rows) {
  const section = document.createElement("details");
  section.className = "capability-domain";
  const head = document.createElement("summary");
  head.textContent = `APP 自身能力面（面板路由 · 不在她的注册表里） · ${rows.length} 条`;
  section.appendChild(head);
  const grid = document.createElement("div");
  grid.className = "quick-strip";
  rows.forEach((row) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "quick-chip";
    chip.dataset.appRoute = row.route;
    chip.title = `${row.method} ${row.route}\n${row.desc}`;
    chip.textContent = `${row.title} · ${row.method}`;
    chip.addEventListener("click", () => {
      // 只报账、不代发请求：这些出口在面板里都已有各自的控件。
      addTimeline(`APP 能力 · ${row.title}`, `${row.method} ${row.route} · ${row.desc}`, "system");
    });
    grid.appendChild(chip);
  });
  section.appendChild(grid);
  return section;
}

// 契约已立、实体未建：如实标"未建"，不做假入口。
function buildPendingSection(rows) {
  const section = document.createElement("details");
  section.className = "capability-domain";
  const head = document.createElement("summary");
  head.textContent = `契约已立 · 实体未建 · ${rows.length} 项`;
  section.appendChild(head);
  const grid = document.createElement("div");
  grid.className = "quick-strip";
  rows.forEach((row) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "quick-chip";
    chip.dataset.pending = row.key;
    chip.textContent = `${row.title} · 未建`;
    chip.title = `${row.title}\n${row.desc}\n卡在：${row.blocked_by}\n`
      + `依据：${(row.evidence || []).join(" · ")}\n${row.note || ""}`;
    chip.addEventListener("click", () => {
      addTimeline(`${row.title} 目前未建`, row.blocked_by, "system");
    });
    grid.appendChild(chip);
  });
  section.appendChild(grid);
  return section;
}

function formatBytes(value) {
  const n = Number(value) || 0;
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v >= 10 ? v.toFixed(0) : v.toFixed(1)} ${units[i]}`;
}

// 取 JSON，并把"HTTP 不是 200"和"网络断了"**分开报**。
// 起因：面板后端是旧版时这三个新接口会返回 404，而我原来写成"连不上就不添噪音"，
// 把 404 一起吞了 —— 于是界面只是"什么都没有"，一个字都不解释。
// 静默失效比报错危险：用户会以为功能没做，而不是以为后端旧了。
async function fetchJsonOrExplain(path, what) {
  let resp;
  try {
    resp = await fetch(path, { cache: "no-store" });
  } catch (error) {
    return { ok: false, reason: "network", error };      // 真连不上：安静
  }
  if (!resp.ok) {
    // **只报一次**：三个接口会同时 404，逐个 toast 会把输入区糊满（离屏截图所见，三条红条叠在一起）。
    if (!app.staleBackendNotified) {
      app.staleBackendNotified = true;
      addTimeline(
        "面板后端是旧版",
        `${what}：${path} → HTTP ${resp.status}。这个路由是新加的，说明面板进程还是旧代码 ——`
          + "双击桌面上的「启动桌面数字人」图标（它先关旧面板再起新的），然后刷新本页。",
        "error",
      );
      toast("面板后端是旧版：请用桌面图标重启面板", "error", 6000);
    }
    return { ok: false, reason: "stale_backend", status: resp.status };
  }
  try {
    return { ok: true, data: await resp.json() };
  } catch (error) {
    return { ok: false, reason: "bad_json", error };
  }
}

// 项目树：只画名字与大小（服务端也只给这两样）。
function buildTreeNodes(node, level) {
  const box = document.createElement("div");
  (node.children || []).forEach((child) => {
    if (child.kind !== "dir") {
      const row = document.createElement("div");
      row.className = "quick-chip";
      row.dataset.file = child.name;
      row.textContent = `${child.name} · ${formatBytes(child.bytes)}`;
      box.appendChild(row);
      return;
    }
    const det = document.createElement("details");
    det.className = "capability-domain";
    if (level < 2 && !child.skipped && !child.collapsed) det.open = true;
    const sum = document.createElement("summary");
    const meta = child.skipped
      ? "已截断（依赖树 / 版本库 / 缓存）"
      : child.collapsed
        ? "更深层未展开"
        : `${child.dirs} 目录 · ${child.files} 文件 · ${formatBytes(child.bytes)}`;
    sum.textContent = `${child.name}/ — ${meta}`;
    det.appendChild(sum);
    if (!child.skipped) det.appendChild(buildTreeNodes(child, level + 1));
    box.appendChild(det);
  });
  if (node.more) {
    const more = document.createElement("div");
    more.className = "quick-chip";
    more.textContent = `… 还有 ${node.more} 项未列`;
    box.appendChild(more);
  }
  return box;
}

// 旁观者（独立观察位）+ 项目树。
// 只读：这里只 GET 两个取证面，**不启动 DSH、不下发任何动作** —— 那是敏感档，等风哥批。
async function setupObserverAndTree(catalog) {
  const strip = document.querySelector(".quick-strip");
  if (!strip || !strip.parentElement) return;
  let status = null;
  let tree = null;
  const [observerResult, treeResult] = await Promise.all([
    fetchJsonOrExplain("/api/observer", "旁观者状态取不到"),
    fetchJsonOrExplain("/api/tree?depth=3&limit=400", "项目树取不到"),
  ]);
  if (observerResult.ok) status = observerResult.data;
  if (treeResult.ok) tree = treeResult.data;
  // 页脚沙箱芯片用同一份读数（同一次请求，不再多打一发）。
  updateSandboxChip(status && status.ok ? (status.sandbox || null) : null);
  if (!status && !tree) return;   // 原因已经在上面的提示里说过了，不再重复刷屏

  const details = document.createElement("details");
  details.className = "capability-catalog";
  details.open = true;                    // 默认展开：折叠着就等于没做（实测被自己坑过）
  const summary = document.createElement("summary");
  summary.textContent = "旁观者（独立观察位） · 项目树";
  details.appendChild(summary);

  const grid = document.createElement("div");
  grid.className = "quick-strip";
  if (status && status.ok) {
    const state = document.createElement("button");
    state.type = "button";
    state.className = "quick-chip";
    state.textContent = `状态 ${status.status} · 握手 ${status.handshake}`;
    state.title = [
      ...(status.contract || []).map((row) => `契约：${row.path}`),
      `DSH 权限预设：${(status.dsh || {}).permission_preset || "未知"}`,
      `3080：${(status.dsh || {}).web_3080}`,
    ].join("\n");
    state.addEventListener("click", () => addTimeline(
      "旁观者状态",
      `${status.status} · 握手 ${status.handshake}（3080 ${(status.dsh || {}).web_3080}）`,
      "system",
    ));
    grid.appendChild(state);
    const sandbox = status.sandbox || {};
    const sandboxChip = document.createElement("button");
    sandboxChip.type = "button";
    sandboxChip.className = "quick-chip";
    sandboxChip.textContent = `只读档 · ${sandbox.read_only_configured ? "已配置" : "未配置"}`;
    sandboxChip.title = [
      `隔离家：${sandbox.isolated_home || "?"}`,
      `settings.defaultPreset：${sandbox.settings_default_preset || "?"}`,
      `patch sandbox：${sandbox.patch_sandbox || "?"}`,
      sandbox.caveat || "",
    ].join("\n");
    sandboxChip.addEventListener("click", () => addTimeline(
      "旁观者只读档",
      `${sandbox.read_only_configured ? "已配置" : "未配置"}`
        + (sandbox.authority ? ` · ${sandbox.authority}` : ""),
      "system",
    ));
    grid.appendChild(sandboxChip);
    (status.blockers || []).forEach((row) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "quick-chip";
      chip.textContent = `卡点 · ${row.code}`;
      chip.title = row.detail;
      chip.addEventListener("click", () => addTimeline(`旁观者卡点 ${row.code}`, row.detail, "system"));
      grid.appendChild(chip);
    });
    (status.sees || []).forEach((row) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "quick-chip";
      chip.textContent = `可见 · ${row.what}`;
      chip.title = `${row.what} · ${row.how} · ${row.mode}`;
      chip.addEventListener("click", () => addTimeline(
        `旁观者可见面 · ${row.what}`, `${row.how}（${row.mode}）`, "system"));
      grid.appendChild(chip);
    });
  }
  details.appendChild(grid);

  // 三件职能分栏（契约第一条：职能只有三件）。空着也如实画出来 —— 那是"还没出声"，不是坏。
  if (status && status.ok) {
    const byKind = status.voice_by_kind || {};
    const labels = ["提醒", "意见", "建议"];
    const voice = document.createElement("details");
    voice.className = "capability-domain";
    const vSum = document.createElement("summary");
    vSum.textContent = "旁观者出声（三件职能） · "
      + labels.map((label) => `${label} ${(byKind[label] || []).length}`).join(" · ");
    voice.appendChild(vSum);
    labels.forEach((label) => {
      const rows = byKind[label] || [];
      const line = document.createElement("div");
      line.className = "quick-chip";
      line.dataset.voice = label;
      line.textContent = rows.length
        ? `${label} · ${rows[rows.length - 1].detail}`
        : `${label} · 还没出声（声源未接：DSH 的 session/prompt 尚未获批）`;
      line.title = rows.length
        ? rows.map((row) => `${row.iso} ${row.detail}`).join("\n")
        : "通道通了，但还没有声音 —— 别把空读成通。";
      voice.appendChild(line);
    });
    details.appendChild(voice);
  }

  if (tree && tree.ok && tree.tree) {
    const head = document.createElement("details");
    head.className = "capability-domain";
    head.open = true;
    const headSum = document.createElement("summary");
    headSum.textContent = `项目树 · ${tree.root} — ${tree.tree.dirs} 目录 / `
      + `${tree.tree.files} 文件 / ${formatBytes(tree.tree.bytes)}`
      + `${tree.truncated ? " · 已截断" : ""}`;
    head.appendChild(headSum);
    head.appendChild(buildTreeNodes(tree.tree, 1));
    details.appendChild(head);
  }

  // 插在芯片区**上面**，而不是它后面 —— 原来放最底部，滚动才看得到，等于白做。
  strip.parentElement.insertBefore(details, strip);
  // 失败隔离（R-H161 · 钩子矩阵红线 2）：卡片出问题**不许连累**已插入的能力总目录
  // **不许静默失败**（R-H169）：出问题必须在**页面上**写红字 —— 只 console.warn 等于没报，
  // 因为"没渲染"和"渲染了"在主人眼里长得一模一样。
  try {
    renderReadonlyCards(catalog, strip);
  } catch (err) {
    cardErrorBox(strip, err, "renderReadonlyCards");
    console.warn("只读卡片渲染失败（能力总目录不受影响）:", err && err.message);
  }
  // 卡③（R-H171）：净化刀读数 —— 异步取数，**失败也不许静默**（自己 catch 自己报红字）
  renderPurgeCard(strip).catch((err) => {
    cardErrorBox(strip, err, "renderPurgeCard");
    console.warn("净化读数卡片渲染失败（能力总目录不受影响）:", err && err.message);
  });
  // 卡④（R-H173）：音乐发布平台三层只读 —— 同样**失败不静默**
  renderMusicCard(strip).catch((err) => {
    cardErrorBox(strip, err, "renderMusicCard");
    console.warn("音乐平台卡片渲染失败（能力总目录不受影响）:", err && err.message);
  });
  // 卡⑤（R-H186）：工作区 —— **全 App 唯一"能干活"的那一块**（①②③④ 只读，这块能执行）
  try {
    renderWorkspace(catalog, strip);
  } catch (err) {
    cardErrorBox(strip, err, "renderWorkspace");
    console.warn("工作区渲染失败（能力总目录不受影响）:", err && err.message);
  }
  // 上帝视角（R-H187）：总览置顶 —— **只呈现，不执行**（整块只用 GET）
  renderOverview(catalog).catch((err) => {
    cardErrorBox(strip, err, "renderOverview");
    console.warn("上帝视角渲染失败（能力总目录不受影响）:", err && err.message);
  });
}

// 上帝视角数字人（R-H187）：**总览 · 只呈现，不执行**，挂在 deck 最顶（#overview-host）。
// 六格：能力位 / 门禁面 / AI 状态 / 活跃告警 / 任务流 / 今日产出（未接入如实标）。
// 🔴 整块只用 GET —— 这里**没有任何 POST**；它不执行、不改变任何状态。
async function renderOverview(catalog) {
  const host = document.getElementById("overview-host");
  if (!host) return;
  host.innerHTML = "";
  const card = document.createElement("details");
  card.className = "capability-catalog";
  card.open = true;
  const sum = document.createElement("summary");
  const items = (catalog && Array.isArray(catalog.items)) ? catalog.items : [];
  const enabled = catalog && catalog.enabled != null ? catalog.enabled : "?";
  const total = catalog && catalog.total != null ? catalog.total : "?";
  sum.textContent = `上帝视角 · 全局总览（能力位 ${enabled}/${total} · 只呈现，不执行）`;
  card.appendChild(sum);
  const row = document.createElement("div");
  row.className = "wf-run";
  row.textContent = "正在取全局读数…";
  card.appendChild(row);
  host.appendChild(card);

  const tiles = [];
  tiles.push(["能力位", `${enabled} / ${total}`, "ok"]);
  const gated = items.filter((r) => r.needs_confirmation).length;
  const disabled = items.filter((r) => !r.enabled).length;
  tiles.push(["门禁面", `需确认 ${gated} · 禁用 ${disabled}`, "unverified"]);
  const st = await fetchJsonOrExplain("/api/state", "面板状态取不到");
  if (st.ok && st.data) {
    const mood = ((st.data.mind || {}).mood) || "未报";
    tiles.push(["AI 状态", `内核 ${st.data.codex_ready ? "就绪" : "未就绪"} · 心智 ${mood}`,
      st.data.codex_ready ? "ok" : "denied"]);
  } else {
    tiles.push(["AI 状态", "取不到", "denied"]);
  }
  const pg = await fetchJsonOrExplain("/api/purge", "净化读数取不到");
  if (pg.ok && pg.data && pg.data.ok) {
    tiles.push(["活跃告警",
      `runtime_faults ${pg.data.runtime_faults} · 报警源 ${pg.data.anomalies}`,
      pg.data.runtime_faults ? "denied" : "ok"]);
  } else {
    tiles.push(["活跃告警", "取不到", "denied"]);
  }
  const tl = document.getElementById("timeline");
  tiles.push(["任务流", `${tl ? tl.children.length : "?"} 条（事件流驱动）`, "unverified"]);
  tiles.push(["今日产出", "未接入（等产出接口）", "unverified"]);

  row.innerHTML = tiles.map(([k, v, cls]) =>
    `<span class="nd ${cls}">${k}：${v}</span>`).join("")
    + `<div style="margin-top:3px;color:var(--muted)">本块只读：六格全走 GET`
    + `（/api/state · /api/purge · /api/capabilities）—— 不执行任何动作。</div>`;
}

// 卡⑤ 工作区（R-H186）：**选能力 + 填参数 + 执行 + 看结果**。
// 出口复用现成的 POST /api/capability（bridge.capability → api.run_task，**过 auth_gate**）。
// 🔴 红线印在卡上：**不可逆动作照卡**（auth_gate 不动）· **可逆动作免卡**（人类视角执行律）。
// 🔴 与只读卡的分界：①②③④ 只读；**只有这块能执行**。
function renderWorkspace(catalog, strip) {
  const zone = document.getElementById("workbench-host");    // R-H187：干的地方（紧贴输入区）
  const host = zone || (strip && strip.parentElement);
  if (!host || !catalog) return;
  let box = document.getElementById("workspace-card");
  if (!box) {
    box = document.createElement("div");
    box.id = "workspace-card";
    if (zone) zone.appendChild(box); else host.insertBefore(box, strip);
  }
  box.innerHTML = "";
  const card = document.createElement("details");
  card.className = "capability-catalog";
  card.open = true;
  const items = (Array.isArray(catalog.items) ? catalog.items : []).filter((r) => r.enabled);
  const sum = document.createElement("summary");
  sum.textContent = `工作区 · 能干活的那一块（${items.length} 个可执行能力 · 只读卡①②③④不执行）`;
  card.appendChild(sum);

  const row = document.createElement("div");
  row.className = "wf-run";
  const sel = document.createElement("select");
  sel.id = "ws-kind";
  items.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.kind;
    opt.textContent = r.needs_confirmation ? `${r.kind}（侧效应 · 需二次确认）` : r.kind;
    sel.appendChild(opt);
  });
  const ta = document.createElement("textarea");
  ta.id = "ws-payload";
  ta.rows = 2;
  ta.placeholder = '{"op":"status"}';
  ta.value = '{"op":"status"}';
  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "ws-run";
  btn.className = "btn";
  btn.textContent = "执行";
  const out = document.createElement("pre");
  out.id = "ws-out";
  out.style.marginTop = "4px";
  out.textContent = "结果会显示在这里（POST /api/capability → run_task · 过 auth_gate）";

  let armed = false;
  btn.addEventListener("click", async () => {
    const picked = items.find((r) => r.kind === sel.value);
    if (!picked) return;
    if (picked.needs_confirmation && !armed) {
      armed = true;
      btn.textContent = "再点一次确认执行";
      window.setTimeout(() => { armed = false; btn.textContent = "执行"; }, 8000);
      return;
    }
    armed = false;
    let payload = {};
    try {
      payload = ta.value.trim() ? JSON.parse(ta.value) : {};
    } catch (err) {
      out.style.color = "var(--alert-quiet)";
      out.textContent = "参数不是合法 JSON：" + (err && err.message);
      return;
    }
    btn.disabled = true;
    btn.textContent = "执行中…";
    try {
      const res = await postJson("/api/capability", {
        kind: sel.value, payload, confirm: !!picked.needs_confirmation,
      });
      out.style.color = res && res.ok ? "var(--success)" : "var(--alert-quiet)";
      out.textContent = JSON.stringify({
        ok: res && res.ok, status: res && res.status, denied: res && res.denied,
        missing: res && res.missing, error: res && res.error, result: res && res.result,
      }, null, 1).slice(0, 1500);
    } catch (err) {
      out.style.color = "var(--alert-quiet)";
      out.textContent = "执行被拒或失败：" + ((err && err.message) || "unknown");
    }
    btn.disabled = false;
    btn.textContent = "执行";
  });

  row.appendChild(sel);
  row.appendChild(ta);
  row.appendChild(btn);
  row.appendChild(out);
  card.appendChild(row);
  const note = document.createElement("div");
  note.style.cssText = "margin-top:4px;color:var(--alert-quiet)";
  note.textContent = "红线：不可逆动作照卡（auth_gate 不动）；可逆动作免卡（人类视角执行律）。"
    + "只读卡①②③④ 不执行——**只有这块能干活**。";
  card.appendChild(note);
  box.appendChild(card);
}

// 卡④ 音乐发布平台 · 三层只读（R-H173）：**只从 /api/music 取数**。
// 🔴 红线印在卡上：全部平台标"未核实" —— **"在"不等于"能用"**；只呈现，不加执行能力。
async function renderMusicCard(strip) {
  const zone = document.getElementById("readonly-host");     // R-H187：读的一律进只读区
  const host = zone || (strip && strip.parentElement);
  if (!host) return;
  let box = document.getElementById("music-card");
  if (!box) {
    box = document.createElement("div");
    box.id = "music-card";
    if (zone) zone.appendChild(box); else host.insertBefore(box, strip);
  }
  box.innerHTML = "";
  const card = document.createElement("details");
  card.className = "capability-catalog";
  card.open = true;
  const sum = document.createElement("summary");
  const res = await fetchJsonOrExplain("/api/music", "音乐平台读数取不到");
  const row = document.createElement("div");
  row.className = "wf-run";
  if (!res.ok || !res.data || !res.data.ok) {
    sum.textContent = "音乐发布平台 · 三层只读 · 取不到";
    sum.style.color = "var(--warning)";
    row.textContent = "数据源 /api/music 不可用（HTTP " + (res.status || "?")
      + "）—— 面板进程还是旧代码，双击桌面「启动桌面数字人」重启后刷新即可。";
    card.appendChild(sum);
    card.appendChild(row);
    box.appendChild(card);
    return;
  }
  const d = res.data;
  const counts = d.counts || {};
  sum.textContent = "音乐发布平台 · 三层只读（共 " + (counts.total || 0) + " 个平台 · "
    + "已核实 " + (counts.verified || 0) + " · 未核实 " + (counts.unverified || 0) + "）";
  card.appendChild(sum);
  const chips = (d.classes || []).map((c) => {
    const names = (c.items || []).map((it) => it.name).join(" / ");
    return `<span class="nd">${c.ring}·${c.cn} ${c.count}：${names}</span>`;
  }).join("");
  row.innerHTML = chips
    + `<div style="margin-top:4px;color:var(--alert-quiet)">红线：<b>全部标『未核实』</b>`
    + ` —— "在"不等于"能用"；本卡只呈现，<b>不加任何执行能力</b>。</div>`
    + `<div style="margin-top:3px;color:var(--muted)">优先集成：${(d.priority || []).join(" → ")}`
    + ` · 数据源：${d.source || "/api/music"}</div>`;
  card.appendChild(row);
  box.appendChild(card);
}

// 卡③ 净化刀 · 读数（R-H171）：**只从 /api/purge 取数**，口径由后端随读数一起给。
// 🔴 红线印在卡上：`anomalies` 是"报警源总量"（含 guard/trace/legacy/recovered），
//    **不是净化成绩**；净化成绩只看 `runtime_faults` —— 谁也不会拿错尺子。
async function renderPurgeCard(strip) {
  const zone = document.getElementById("readonly-host");     // R-H187：同上
  const host = zone || (strip && strip.parentElement);
  if (!host) return;
  let box = document.getElementById("purge-card");
  if (!box) {
    box = document.createElement("div");
    box.id = "purge-card";
    if (zone) zone.appendChild(box); else host.insertBefore(box, strip);
  }
  box.innerHTML = "";
  const card = document.createElement("details");
  card.className = "capability-catalog";
  card.open = true;
  const sum = document.createElement("summary");
  const res = await fetchJsonOrExplain("/api/purge", "净化读数取不到");
  const row = document.createElement("div");
  row.className = "wf-run";
  if (!res.ok || !res.data || !res.data.ok) {
    // 旧面板进程（路由还没加载）也走这里：**看得见**地说明白，不装作没这回事
    sum.textContent = "净化刀 · 读数 · 取不到";
    sum.style.color = "var(--warning)";
    row.textContent = "数据源 /api/purge 不可用（HTTP " + (res.status || "?")
      + "）—— 面板进程还是旧代码，双击桌面「启动桌面数字人」重启面板后刷新即可。";
    card.appendChild(sum);
    card.appendChild(row);
    box.appendChild(card);
    return;
  }
  const d = res.data;
  const bs = d.by_signal || {};
  const before = d.before || {};
  sum.textContent = "净化刀 · 读数（窗口 " + (d.window || "?") + " 条）"
    + " · 净化成绩 runtime_faults " + d.runtime_faults;
  card.appendChild(sum);
  row.innerHTML =
      `<span class="nd ok">净化成绩 runtime_faults ${d.runtime_faults}</span>`
    + `<span class="nd">报警源总量 anomalies ${d.anomalies}</span>`
    + `<span class="nd unverified">runtime ${bs.runtime || 0}</span>`
    + `<span class="nd">guard ${bs.guard || 0}</span>`
    + `<span class="nd">trace ${bs.trace || 0}</span>`
    + `<span class="nd">legacy ${bs.legacy || 0}</span>`
    + `<span class="nd">recovered ${bs.recovered || 0}</span>`
    + `<div style="margin-top:4px;color:var(--alert-quiet)">口径：anomalies 含 guard/trace/legacy/recovered`
    + `（连"已恢复"也含）—— 它是报警源总量，<b>不是净化成绩</b>；成绩只看 runtime_faults。</div>`
    + `<div style="margin-top:3px;color:var(--muted)">净化前 runtime_faults ${before.runtime_faults}`
    + `（${before.at} · ${before.source}） → 今 ${d.runtime_faults}</div>`
    + `<div style="margin-top:3px;color:var(--muted)">数据源：${d.source || "/api/purge"}`
    + `（只读，不绕过 API 摸底层）</div>`;
  card.appendChild(row);
  box.appendChild(card);
}

// 只读卡片的**可见失败提示**（R-H169）：渲染挂了就在页面上直说 ——
// 写清"不是没有卡片，是画不出来"，并把原因和位置一并写出来（不留在控制台里）。
function cardErrorBox(strip, err, where) {
  const host = strip && strip.parentElement;
  if (!host) return;
  let box = document.getElementById("card-error");
  if (!box) {
    box = document.createElement("div");
    box.id = "card-error";
    host.insertBefore(box, strip);
  }
  box.innerHTML = "";
  const card = document.createElement("details");
  card.className = "capability-catalog";
  card.open = true;
  const sum = document.createElement("summary");
  sum.textContent = "只读卡片渲染失败 · 不是\"没有卡片\"，是\"画不出来\""
                    + (where ? "（" + where + "）" : "");
  sum.style.color = "var(--alert-quiet)";
  card.appendChild(sum);
  const body = document.createElement("div");
  body.className = "wf-run";
  body.textContent = "原因：" + ((err && err.message) || String(err))
    + " —— 位置：holo_pet/app.js 的 " + (where || "渲染段")
    + "。修掉它，卡片就回到输入框上方这一排。";
  card.appendChild(body);
  box.appendChild(card);
}

// 只读卡片（R-H159）：投影卡片 + 穿透网七栏 —— **只从 /api/capabilities 的目录取数**，
// 不直连 store、不加任何执行能力（与 launcher_inventory / 沙盘同口径：只呈现，不执行）。
function renderReadonlyCards(catalog, strip) {
  // R-H187：卡片挂到**设计好的位置**（#readonly-host），不再塞进 form.composer。
  // 老页面没有 host 时兜底回原处 —— 改布局不许把卡片弄丢。
  const zone = document.getElementById("readonly-host");
  const host = zone || (strip && strip.parentElement);
  if (!host || !catalog) return;
  const place = (el) => { if (zone) zone.appendChild(el); else host.insertBefore(el, strip); };
  // 可见信标（R-H169）：**看得到这一行 = 新代码真的在跑**（看不到 = 没刷新 / 没跑到这里）。
  // 这一行的作用不是装饰，是给主人一个不用猜的信号。
  let badge = document.getElementById("readonly-cards-badge");
  if (!badge) {
    badge = document.createElement("div");
    badge.id = "readonly-cards-badge";
    place(badge);
  }
  badge.className = "nd ok";
  badge.textContent = "只读卡片 R-H187 · 渲染成功（位置：设计好的「只读区」· 数据源 /api/capabilities + /api/purge + /api/music · 只读 · 不执行）";
  const mk = (id, title) => {
    let box = document.getElementById(id);
    if (!box) {
      box = document.createElement("div");
      box.id = id;
      place(box);
    }
    const card = document.createElement("details");
    card.className = "capability-catalog";
    card.open = true;
    const sum = document.createElement("summary");
    sum.textContent = title;
    card.appendChild(sum);
    box.appendChild(card);
    return card;
  };

  // ① 空间投射 · 只读卡片：5 原语全标未核实 + ARM ≠ LIVE 红线
  const proj = mk("proj-card", "空间投射 · 只读卡片（5/5 未核实）");
  const pv = document.createElement("div");
  pv.className = "wf-run";
  const prims = ["采集 CAPTURE", "遮罩 MASK", "映射 MAP", "融合 FUSE", "输出 OUTPUT"];
  pv.innerHTML = prims.map((n) => `<span class="nd unverified">${n} · 未核实</span>`).join(" → ")
    + `<div style="margin-top:4px">红线：<span class="nd denied">ARM ≠ LIVE</span>`
    + `<span class="nd">准备态永不点亮</span>`
    + `<span class="nd">硬件门禁未全绿不 LIVE</span></div>`
    + `<div style="color:var(--muted);margin-top:3px">技能定义：gbt_allinone/tools/projection_skill.py（只读 · 不执行）</div>`;
  proj.appendChild(pv);

  // ② 穿透网 · 七栏读数（从目录派生；**未核实就标未核实**）
  const items = Array.isArray(catalog.items) ? catalog.items : [];
  const enabled = items.filter((row) => row.enabled);
  const disabled = items.filter((row) => !row.enabled);
  const domains = new Set(items.map((row) => String(row.domain || "")).filter(Boolean));
  const net = mk("net-seven", `穿透网 · 七栏读数（共 ${items.length} 位）`);
  const nv = document.createElement("div");
  nv.className = "wf-run";
  nv.innerHTML =
      `<span class="nd">indexed ${items.length}</span>`
    + `<span class="nd ok">enabled ${enabled.length}</span>`
    + `<span class="nd denied">disabled ${disabled.length}</span>`
    + `<span class="nd">domains ${domains.size}</span>`
    + `<span class="nd unverified">penetrate_ready 0</span>`
    + `<div style="margin-top:3px;color:var(--muted)">数据源：/api/capabilities（total/items/domains）· 只读，不加执行能力</div>`;
  net.appendChild(nv);
}

async function setupCapabilityCatalog() {
  const strip = document.querySelector(".quick-strip");
  if (!strip || !strip.parentElement) return null;
  let catalog = null;
  const catalogResult = await fetchJsonOrExplain("/api/capabilities", "能力总目录取不到");
  if (!catalogResult.ok) return null;   // 原因已经提示过
  catalog = catalogResult.data;
  if (!catalog || !catalog.ok || !Array.isArray(catalog.items)) return null;

  const enabled = catalog.items.filter((row) => row.enabled);
  const disabled = catalog.items.filter((row) => !row.enabled);
  const gated = enabled.filter((row) => row.needs_confirmation);
  const appBlock = catalog.app || {};
  const appRoutes = Array.isArray(appBlock.routes) ? appBlock.routes : [];
  const appPending = Array.isArray(appBlock.pending) ? appBlock.pending : [];
  const details = document.createElement("details");
  details.className = "capability-catalog";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent =
    `能力总目录 · 共 ${catalog.total} 项`
    + `（可用 ${enabled.length} · 需确认 ${gated.length} · 被禁用 ${disabled.length}）`
    + ` · APP 自身 ${appRoutes.length} 条 · 待建 ${appPending.length}`;
  details.appendChild(summary);

  const armed = new Set();
  // 按域分类：域内项数多的排前面，同数量按域名字典序。
  const byDomain = new Map();
  enabled.forEach((row) => {
    const key = String(row.domain || "").trim() || "other";
    if (!byDomain.has(key)) byDomain.set(key, []);
    byDomain.get(key).push(row);
  });
  [...byDomain.keys()]
    .sort((a, b) => byDomain.get(b).length - byDomain.get(a).length || a.localeCompare(b))
    .forEach((domain) => {
      const rows = byDomain.get(domain);
      const section = document.createElement("details");
      section.className = "capability-domain";
      const head = document.createElement("summary");
      head.textContent = `${domainLabel(domain)} · ${rows.length} 项`;
      section.appendChild(head);
      section.appendChild(buildCapabilityChips(rows, armed));
      details.appendChild(section);
    });

  if (disabled.length) details.appendChild(buildDisabledSection(disabled));
  if (appRoutes.length) details.appendChild(buildAppSurfaceSection(appRoutes));
  if (appPending.length) details.appendChild(buildPendingSection(appPending));
  strip.parentElement.insertBefore(details, strip);
  return catalog;
}

// 视频工坊（自作电影）：工具就绪度 + 最火的几家短视频平台。
// 数据全来自 /api/studio：工具是**实测**的 bin/env，平台事实只读她那本登记表。
async function setupStudio() {
  const strip = document.querySelector(".quick-strip");
  if (!strip || !strip.parentElement) return;
  const res = await fetchJsonOrExplain("/api/studio", "视频工坊取不到");
  if (!res.ok) return;
  const data = res.data;
  if (!data || !data.ok) return;

  const tools = data.tools || [];
  const plats = data.platforms || [];
  const readyTools = tools.filter((t) => t.ready).length;

  const details = document.createElement("details");
  details.className = "capability-catalog";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = `视频工坊（自作电影） · 工具 ${readyTools}/${tools.length} 就绪`
    + ` · 平台 ${plats.length} 家（登记表共 ${data.platforms_tracked_total ?? "?"}）`;
  details.appendChild(summary);

  const grid = document.createElement("div");
  grid.className = "quick-strip";
  tools.forEach((tool) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "quick-chip";
    chip.dataset.studioTool = tool.id;
    chip.textContent = `${tool.label} · ${tool.ready ? "就绪" : "缺 " + (tool.missing || []).join("/")}`;
    chip.title = `${tool.label}\n${tool.what}\n${tool.ready
      ? "依赖齐：可直接用"
      : "缺：" + (tool.missing || []).join("、")}`;
    chip.addEventListener("click", () => addTimeline(
      `视频工坊 · ${tool.label}`,
      tool.ready ? "依赖齐，可直接用" : `缺 ${(tool.missing || []).join("、")}`,
      tool.ready ? "system" : "warn",
    ));
    grid.appendChild(chip);
  });
  details.appendChild(grid);

  const platformGrid = document.createElement("div");
  platformGrid.className = "quick-strip";
  plats.forEach((p) => {
    const gates = p.gates || {};
    const open = (data.gate_names || []).filter((g) => gates[g]).length;
    const api = p.official_api === true
      ? "官方接口 · 有"
      : p.official_api === false ? "无官方接口" : "接口未记录";
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "quick-chip";
    chip.dataset.studioPlatform = p.id;
    chip.textContent = `${p.label} · ${api} · 门禁 ${open}/4`;
    chip.title = [
      p.label,
      `官方接口：${p.official_api === true ? "有" : p.official_api === false ? "无（本舱区不做，也不绕）" : "登记表未记录"}`,
      p.delivery ? `投递：${p.delivery}` : "",
      p.audit_gate ? `资质闸：${p.audit_gate}` : "",
      p.credential_field ? `凭据字段：${p.credential_field}` : "",
      `门禁：${open}/4 已登记（应用/权限/授权/凭据）`,
    ].filter(Boolean).join("\n");
    chip.addEventListener("click", () => addTimeline(
      `发布平台 · ${p.label}`,
      `${api} · 门禁 ${open}/4${p.credential_field ? " · 凭据字段 " + p.credential_field : ""}`,
      p.official_api === false ? "warn" : "system",
    ));
    platformGrid.appendChild(chip);
  });
  details.appendChild(platformGrid);

  const doc = data.checklist || {};
  if (doc.exists) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "quick-chip";
    chip.dataset.studioChecklist = "1";
    chip.textContent = `接入单 · ${Math.round((doc.bytes || 0) / 1024)} KB`;
    chip.title = `最火的几家的官方入口 / 资质闸 / 凭据字段 / 四道闸怎么过\n${doc.path}`;
    chip.addEventListener("click", () => addTimeline(
      "短视频平台接入单",
      `${doc.rel} —— 每家的官方入口、资质闸、凭据字段、四道闸怎么过都在里面`,
      "system",
    ));
    details.appendChild(chip);
  }

  strip.parentElement.insertBefore(details, strip);
}

function setupBluetooth() {
  $("#bt-scan").addEventListener("click", () => bluetoothRequest(
    "scan",
    { timeout: 6 },
    "正在扫描附近设备",
  ));
  $("#bt-classic").addEventListener("click", () => bluetoothRequest(
    "classic",
    {},
    "正在读取已配对设备",
  ));
  $("#bt-clear-services").addEventListener("click", () => {
    $("#bt-services").hidden = true;
    app.selectedCharacteristic = null;
    $("#bt-write-console").hidden = true;
    $("#bt-write-confirm").hidden = true;
  });
  $("#bt-write-request").addEventListener("click", requestBluetoothWrite);
  $("#bt-write-cancel").addEventListener("click", () => {
    $("#bt-write-confirm").hidden = true;
    app.pendingWrite = null;
  });
  $("#bt-write-confirm-yes").addEventListener("click", () => {
    const pending = app.pendingWrite;
    if (!pending) return;
    $("#bt-write-confirm").hidden = true;
    bluetoothRequest("write", {
      address: pending.address,
      char_uuid: pending.uuid,
      value_hex: pending.value_hex,
      confirm: true,
    }, "正在执行受控写入");
    app.pendingWrite = null;
  });
}

function setupVoiceControls() {
  setupVoiceInput();
  microphoneButton.addEventListener("click", () => {
    if (!app.recognizer) return;
    app.voiceConversation = !app.voiceConversation;
    microphoneButton.title = app.voiceConversation ? "停止连续语音对话" : "开始连续语音对话";
    if (!app.voiceConversation) {
      window.clearTimeout(app.voiceRestartTimer);
      if (app.recognitionActive) app.recognizer.stop();
      toast("连续语音对话已停止");
    } else {
      app.speechOutput = true;
      voiceOutputButton.setAttribute("aria-pressed", "true");
      scheduleVoiceRestart(0);
      toast("连续语音对话已开启");
    }
  });
  voiceOutputButton.addEventListener("click", () => {
    app.speechOutput = !app.speechOutput;
    voiceOutputButton.setAttribute("aria-pressed", app.speechOutput ? "true" : "false");
    if (!app.speechOutput && "speechSynthesis" in window) window.speechSynthesis.cancel();
    toast(app.speechOutput ? "语音播报已开启" : "语音播报已关闭");
  });
}

function setupDragging() {
  let startX = 0;
  let startY = 0;
  let baseX = 0;
  let baseY = 0;

  dragHandle.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
    startX = event.clientX;
    startY = event.clientY;
    baseX = app.drag?.x || 0;
    baseY = app.drag?.y || 0;
    app.drag = { x: baseX, y: baseY };
    dragHandle.setPointerCapture(event.pointerId);
    document.body.classList.add("is-dragging");
  });

  dragHandle.addEventListener("pointermove", (event) => {
    if (!app.drag) return;
    const nextX = baseX + event.clientX - startX;
    const nextY = baseY + event.clientY - startY;
    const rect = shell.getBoundingClientRect();
    const maxX = Math.max(0, (window.innerWidth - rect.width) / 2);
    const maxY = Math.max(0, (window.innerHeight - rect.height) / 2);
    app.drag.x = Math.max(-maxX, Math.min(maxX, nextX));
    app.drag.y = Math.max(-maxY, Math.min(maxY, nextY));
    shell.style.transform = `translate3d(${app.drag.x}px, ${app.drag.y}px, 0)`;
  });

  const endDrag = () => {
    if (!app.drag) return;
    document.body.classList.remove("is-dragging");
    try {
      localStorage.setItem("gbt-holo-position", JSON.stringify(app.drag));
    } catch {
      // Storage can be unavailable in hardened browser profiles.
    }
  };
  dragHandle.addEventListener("pointerup", endDrag);
  dragHandle.addEventListener("pointercancel", endDrag);

  try {
    const saved = JSON.parse(localStorage.getItem("gbt-holo-position") || "{}");
    if (Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
      app.drag = { x: saved.x, y: saved.y };
      shell.style.transform = `translate3d(${saved.x}px, ${saved.y}px, 0)`;
    }
  } catch {
    app.drag = null;
  }

  let idleTimer = null;
  const wake = () => {
    document.body.classList.remove("is-idle");
    window.clearTimeout(idleTimer);
    idleTimer = window.setTimeout(() => document.body.classList.add("is-idle"), 9000);
  };
  window.addEventListener("pointermove", wake, { passive: true });
  wake();
}

// 页脚「沙箱」芯片：**只报真读到的策略**。
// 以前这里写死一句「沙箱：工作区可写」——它夹在一排会实时更新的芯片中间，
// 看着像实时读数，其实无论策略如何都恒显示"可写"，属于假的肯定态。
// 真值走 /api/observer（bridge.observer 读 settings.defaultPreset 与 cordis patch）。
// 拿不到就如实报"未知"，按本仓红线不静默降级成肯定式断言。
function updateSandboxChip(sandbox) {
  const chip = $("#chip-sandbox");
  if (!chip) return;
  if (!sandbox) {
    setChipLabel(chip, "沙箱 · 未知（observer 读不到）");
    chip.classList.add("status-chip--warn");
    chip.title = "/api/observer 读不到 —— 状态未知，不推断。";
    return;
  }
  const preset = sandbox.read_only_configured
    ? "read-only"
    : (sandbox.settings_default_preset || sandbox.patch_sandbox || "");
  setChipLabel(chip, preset ? `沙箱 · ${preset}` : "沙箱 · 未配置");
  chip.classList.toggle("status-chip--warn", Boolean(sandbox.read_only_configured));
  chip.title = [
    `settings.defaultPreset：${sandbox.settings_default_preset || "未配置"}`,
    `cordis patch sandbox：${sandbox.patch_sandbox || "无"}`,
    `read-only 已配置：${sandbox.read_only_configured ? "是" : "否"}`,
    sandbox.authority || "",
    sandbox.caveat || "",
  ].filter(Boolean).join("\n");
}

const localAvatar = { source: "local", state: "idle" };

function setLocalAvatarState(state, detail = "") {
  const fallback = $("#stage-fallback");
  if (!fallback || localAvatar.source !== "local") return;
  localAvatar.state = state || "idle";
  fallback.dataset.state = localAvatar.state;
  const labels = {
    idle: "永久免费本地运行 · 待命",
    listening: "正在听你说话",
    thinking: "正在思考与执行",
    speaking: "正在播报",
    happy: "心情很好",
    alert: "需要你的注意",
  };
  const reason = $("#fallback-reason");
  if (reason) reason.textContent = detail || labels[localAvatar.state] || labels.idle;
}

function syncAvatarSourceButtons() {
  const localButton = $("#btn-avatar-local");
  const xingyunButton = $("#btn-avatar-xingyun");
  const localActive = localAvatar.source === "local";
  [localButton, xingyunButton].forEach((button) => button && button.classList.remove("is-active"));
  if (localButton) {
    localButton.classList.toggle("is-active", localActive);
    localButton.setAttribute("aria-pressed", localActive ? "true" : "false");
  }
  if (xingyunButton) {
    xingyunButton.classList.toggle("is-active", !localActive);
    xingyunButton.setAttribute("aria-pressed", localActive ? "false" : "true");
  }
}

function showAvatarFallback(reasonText, tone = "warn") {
  localAvatar.source = "local";
  const fallback = $("#stage-fallback");
  if (fallback) fallback.classList.remove("is-hidden");
  const layer = $("#xingyun-layer");
  if (layer) layer.hidden = true;
  setLocalAvatarState("idle", reasonText || "永久免费本地运行 · 待命");
  syncAvatarSourceButtons();
  setAvatarStatus("本地数字人在线", tone === "error" ? "warn" : "live");
}

const XINGYUN_SDK_URL = "./xingyun_e2e.latest.js";

// ── HUD 响应体 Hook（五条附加条件全带：白名单硬编码 / 只读副本 / 失败静默 /
//    SDK 兼容开关 / 捕获留痕 / 重试联动数据驱动）──
const HUD_RESPONSE_BODY_HOOK = true;                          // SDK 兼容开关：false 即整层退役
const HUD_HOOK_URL_MARKERS = ["/user/v1/ttsa_v2/session"];    // 纯字符串包含，无正则
const HUD_CODE_CLASS = { 5: "waitable", 4: "network" };       // 业务码 → 类别
const HUD_RETRY_POLICY = { waitable: 1, network: 3, default: 3 };
// 10005 = SDK 的"浏览器能力检查失败"。实测本机上它就是**本机渲染**问题：
// 面板的裸 WebGL2 探测通过，但 SDK 用 failIfMajorPerformanceCaveat 严判 ⇒
// 软件渲染（Microsoft Basic Render Driver）被主动拒。把这句写成实话，别让主人去查网络。
const HUD_ERROR_TEXT = { 5: "积分不足，请充值", 4: "凭据签名错误",
                         10005: "本机 3D 渲染不满足要求（星云要求硬件加速的 WebGL2）" };
const hudBusiness = { code: null, reason: "", sessionId: "", at: "" };
// SDK 的 onMessage 是**另一条通道**（不是 fetch 响应）：本机实测它才是 10005 的出处
// （"浏览器能力检查失败: 浏览器不支持 WebGL2"）。不接这条，渲染门就永远判不出来。
const sdkNotice = { code: null, message: "" };

function hudClassify(code) {
  const cls = HUD_CODE_CLASS[code] || "default";
  return { class: cls, retries: HUD_RETRY_POLICY[cls] ?? HUD_RETRY_POLICY.default };
}

function hudRetryLimit() {
  const cls = hudBusiness.code === null ? "default" : hudClassify(hudBusiness.code).class;
  return HUD_RETRY_POLICY[cls] ?? HUD_RETRY_POLICY.default;
}

function hudDescribe(code, reason) {
  return HUD_ERROR_TEXT[code] || `业务错误 ${code}：${reason || "未提供原因"}`;
}

// ── 本机渲染门判据（结构性失败 vs 可重试失败：前者重试只是烧时间）──
const RENDER_GATE_CODE = 10005;
const RENDER_GATE_MARKERS = ["WebGL2", "能力检查", "不支持"];

function isCapabilityGateFailure(error, business) {
  if (business && business.code === RENDER_GATE_CODE) return true;
  if (sdkNotice.code === RENDER_GATE_CODE) return true;
  if (RENDER_GATE_MARKERS.some((marker) => sdkNotice.message.includes(marker))) return true;
  const text = String((error && error.message) || error || "");
  if (RENDER_GATE_MARKERS.some((marker) => text.includes(marker))) return true;
  // 最后一道实证：SDK 的门就是"严格模式 WebGL2"（failIfMajorPerformanceCaveat）。
  // 它拿不到上下文 ⇒ 这台机器上星云形象**结构上起不来**，重试与改网都无意义。
  return rendererStrictlyUnavailable();
}

function rendererStrictlyUnavailable() {
  try {
    return !document.createElement("canvas")
      .getContext("webgl2", { failIfMajorPerformanceCaveat: true });
  } catch (error) {
    return true;   // 抛异常 = 拿不到 ⇒ 同样按不可用处理，并已由 describeRendererGate 留痕
  }
}

function describeRendererGate() {
  // 读**真实渲染器名**当证据；读不到就如实写 unknown，不猜
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) return "本机取不到 WebGL 上下文（renderer=unknown）";
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    const name = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || "") : "";
    const strict = document.createElement("canvas")
      .getContext("webgl2", { failIfMajorPerformanceCaveat: true });
    return `renderer=${name || "unknown"}；严格模式 WebGL2=${strict ? "可用" : "不可用（被判重大性能缺陷）"}`;
  } catch (error) {
    return `渲染器探测失败：${String((error && error.message) || error)}`;
  }
}

function installHudResponseHook() {
  if (!HUD_RESPONSE_BODY_HOOK || typeof window.fetch !== "function") return;
  if (window.__hudResponseHookInstalled) return;
  window.__hudResponseHookInstalled = true;
  const originalFetch = window.fetch;
  window.fetch = async function hudPatchedFetch(input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const hit = HUD_HOOK_URL_MARKERS.some((marker) => String(url).includes(marker));
    const response = await originalFetch.call(this, input, init);
    if (!hit) return response;                      // 非目标请求：原样放行
    try {
      const body = await response.clone().json();   // 只读副本，不改动原响应
      const data = (body && body.data) || {};
      const code = body ? body.error_code : undefined;
      const reason = (body && body.error_reason) || "";
      const sessionId = data.session_id || (body && body.session_id) || "";
      hudBusiness.code = typeof code === "number" ? code : null;
      hudBusiness.reason = reason;
      hudBusiness.sessionId = sessionId;
      hudBusiness.at = new Date().toISOString();
      const summary = code === 0 ? "ok" : hudDescribe(code, reason);
      addTimeline("星云会话响应",
        `code=${code} ${summary}`.trim() + (sessionId ? ` · session=${String(sessionId).slice(0, 20)}` : ""),
        code === 0 ? "system" : "warn");
    } catch (error) {
      // 失败静默：只留一句 debug，不抛、不阻塞、不影响主链路
      console.warn("[holo_pet] hud hook swallow:", (error && error.message) || error);
    }
    return response;                                // 永远返回原始响应
  };
}

const xingyun = {
  phase: "idle",
  agent: null,
  sdkPromise: null,
  progress: 0,
  micActive: false,
  lastReply: "",
};

function setXingyunHud(text, tone = "warn") {
  const hud = $("#xingyun-hud");
  if (!hud) return;
  hud.dataset.tone = tone;
  $("#xingyun-hud-text").textContent = String(text || "");
}

function setXingyunProgress(value) {
  const pct = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  xingyun.progress = pct;
  const bar = $("#xingyun-progress");
  const label = $("#xingyun-progress-text");
  if (bar) bar.style.width = `${pct}%`;
  if (label) label.textContent = `${pct}%`;
}

function setXingyunMic(active) {
  xingyun.micActive = Boolean(active);
  const button = $("#btn-xy-mic");
  if (button) button.setAttribute("aria-pressed", xingyun.micActive ? "true" : "false");
  voiceRipple.classList.toggle("is-open", xingyun.micActive || app.recognitionActive);
}

function loadXingyunSdk() {
  if (window.XingyunAvatarAgent) return Promise.resolve(window.XingyunAvatarAgent);
  if (xingyun.sdkPromise) return xingyun.sdkPromise;
  xingyun.sdkPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = XINGYUN_SDK_URL;
    script.async = true;
    script.onload = () => {
      if (window.XingyunAvatarAgent) resolve(window.XingyunAvatarAgent);
      else reject(new Error("星云 SDK 已加载但没有暴露构造器"));
    };
    script.onerror = () => reject(new Error("星云 SDK 文件加载失败，检查 holo_pet 下的本地包"));
    document.head.appendChild(script);
  }).catch((error) => {
    xingyun.sdkPromise = null;
    throw error;
  });
  return xingyun.sdkPromise;
}

async function stopXingyun(reason = "manual") {
  const agent = xingyun.agent;
  xingyun.agent = null;
  xingyun.phase = "idle";
  setXingyunMic(false);
  if (!agent) return;
  try {
    if (typeof agent.stopASR === "function") await agent.stopASR().catch(() => {});
    if (typeof agent.destroy === "function") await agent.destroy(reason);
  } catch (error) {
    console.warn("[holo_pet] xingyun destroy failed:", error);
  }
}

function handleXingyunUtterance(result) {
  const text = String((result && result.text) || "").trim();
  if (!text) return;
  input.value = text;
  resizeComposer();
  pulseSense("ear", 1600);
  if (!result || !result.isFinal) return;
  if (/^(停止|打断|别说了|停一下)/.test(text)) {
    void interruptCurrentTask();
    return;
  }
  if (/^(新会话|新对话|重开一个)/.test(text)) {
    void startNewThread();
    return;
  }
  const sendMatch = text.match(/^(发送|执行|开始做|去做)[,，:：\s]+(.+)$/);
  if (sendMatch) {
    void sendMessage(sendMatch[2]);
    return;
  }
  toast("语音已转成文字，确认后发送", "info");
}

async function startXingyun() {
  if (xingyun.phase === "connecting" || xingyun.phase === "running") return;
  const layer = $("#xingyun-layer");
  if (layer) layer.hidden = false;
  xingyun.phase = "connecting";
  setXingyunHud("正在申请星云会话", "warn");
  setXingyunProgress(0);
  setAvatarStatus("正在连接星云数字人", "warn");

  let session = null;
  try {
    session = await postJson("/api/xingyun", { op: "session" });
  } catch (error) {
    session = { ok: false, error: `会话申请失败：${error.message}` };
  }

  if (!session || session.ok !== true) {
    const detail = String((session && session.error) || "星云应用凭证未配置");
    xingyun.phase = "unconfigured";
    setXingyunHud(detail, "error");
    setAvatarStatus("星云数字人未连接", "error");
    addTimeline("星云数字人未连接", detail, "error");
    toast(`${detail}，已显示降级形象`, "error");
    showAvatarFallback(detail, "error");
    return;
  }

  let Ctor = null;
  try {
    Ctor = await loadXingyunSdk();
  } catch (error) {
    xingyun.phase = "failed";
    setXingyunHud(error.message, "error");
    setAvatarStatus("星云 SDK 不可用", "error");
    addTimeline("星云 SDK 不可用", error.message, "error");
    return;
  }

  let agent = null;
  let lastError = null;
  // 重试次数由 HUD 捕获的业务码类别决定（waitable=1 / network=3 / default=3，数据驱动）
  for (let attempt = 1; attempt <= hudRetryLimit(); attempt += 1) {
    try {
      agent = new Ctor({
      container: $("#xingyun-viewport"),
      appId: session.appId,
      appSecret: session.appSecret,
      gatewayServer: session.gatewayServer,
      onMessage: (error) => {
        sdkNotice.code = (error && typeof error.code === "number") ? error.code : sdkNotice.code;
        sdkNotice.message = String((error && error.message) || sdkNotice.message || "");
        setXingyunHud(`渲染告警 ${error && error.code ? error.code : ""}`.trim(), "error");
      },
      agentCallbacks: {
        onAgentStateChange: (state) => {
          if (state === "running") {
            xingyun.phase = "running";
            setXingyunHud("星云数字人在线", "live");
            setAvatarStatus("星云数字人在线", "live");
          } else if (state === "failed") {
            xingyun.phase = "failed";
            setXingyunHud("星云连接已断开", "error");
            setAvatarStatus("星云数字人已断开", "error");
          } else if (state === "reconnecting") {
            setXingyunHud("星云链路重连中", "warn");
          }
        },
        onConversationChange: (event) => {
          const state = String((event && event.state) || "");
          if (state === "speaking-directly" || state === "speaking") {
            pulseSense("mouth", 2200);
            setXingyunHud("正在播报", "live");
          } else if (state === "asking") {
            pulseSense("brain", 2200);
            setXingyunHud("正在理解你", "warn");
          } else if (state === "interrupted") {
            setXingyunHud("播报已打断", "warn");
          } else if (state === "failed") {
            setXingyunHud("本轮交互失败", "error");
          }
        },
        onASRResult: (result) => handleXingyunUtterance(result),
        onError: (error) => {
          const detail = `${error && error.domain ? error.domain : "sdk"} · ${error && error.message ? error.message : "未知错误"}`;
          setXingyunHud(detail, "error");
          addTimeline("星云数字人异常", detail, "error");
        },
      },
    });
    xingyun.agent = agent;
    await agent.init({
      onDownloadProgress: (progress) => setXingyunProgress(progress),
    });
    xingyun.phase = "running";
    setXingyunProgress(100);
    setXingyunHud("星云数字人在线", "live");
    setAvatarStatus("星云数字人在线", "live");
    addTimeline("星云数字人已连接", "实时具身形象就绪，可直接对话", "success");
      return;
  } catch (error) {
      lastError = error;
      xingyun.agent = null;
      console.error("[holo_pet] xingyun init error " + JSON.stringify({
        name: error && error.name,
        code: error && (error.agentCode || error.code),
        message: String((error && error.message) || error).slice(0, 300),
        stack: String((error && error.stack) || "").slice(0, 300),
      }));
      if (agent && typeof agent.destroy === "function") {
        try {
          await agent.destroy("init_retry");
        } catch (destroyError) {
          console.warn("[holo_pet] xingyun cleanup failed:", destroyError);
        }
      }
      agent = null;
      const detail = String((error && error.message) || error);
      // 结构性失败（本机渲染门）当场停手：重试三次换来的是 12 秒空等 + 一样的结局
      if (isCapabilityGateFailure(error, hudBusiness)) {
        addTimeline("星云形象不可用（本机渲染限制）", describeRendererGate(), "error");
        break;
      }
      if (attempt < hudRetryLimit()) {
        setXingyunHud(`第 ${attempt} 次连接失败，稍后重试：${detail}`, "warn");
        addTimeline(`星云连接重试（第 ${attempt} 次）`, detail, "warn");
        await new Promise((resolve) => window.setTimeout(resolve, 4000));
      }
    }
  }
  xingyun.phase = "failed";
  const finalDetail = String((lastError && lastError.message) || lastError || "未知错误");
  // 本机渲染门挡住 ⇒ 不装作"连接失败"，如实说原因并**显示纯样式降级形象**，
  // 否则舞台会永远停在"正在检查 3D 渲染引擎"（主人两次说"还是空白"就是这一格）。
  if (isCapabilityGateFailure(lastError, hudBusiness)) {
    const why = describeRendererGate();
    setXingyunHud("本机 3D 渲染不满足星云要求（需硬件加速 WebGL2）", "error");
    addTimeline("星云形象不可用：本机渲染限制", why, "error");
    toast("星云形象需硬件加速 WebGL2；本机是软件渲染，已显示降级形象", "warn", 7000);
    showAvatarFallback("星云数字人需硬件加速 WebGL2（本机为软件渲染）", "warn");
    return;
  }
  // 文案优先级：业务码文案 > SDK 模糊文案（前者是证据，后者只是症状）
  if (typeof hudBusiness.code === "number" && hudBusiness.code !== 0) {
    setXingyunHud(hudDescribe(hudBusiness.code, hudBusiness.reason), "error");
  } else {
    setXingyunHud(`连接失败：${finalDetail}`, "error");
  }
  setAvatarStatus("星云数字人连接失败", "error");
  addTimeline("星云数字人连接失败", finalDetail, "error");
  toast("星云数字人连接失败，已显示降级形象", "error", 6000);
  showAvatarFallback("星云数字人连接失败", "error");
}

function startXingyunAvatar() {
  localAvatar.source = "xingyun";
  syncAvatarSourceButtons();
  const layer = $("#xingyun-layer");
  const fallback = $("#stage-fallback");
  if (fallback) fallback.classList.add("is-hidden");
  if (layer) layer.hidden = false;
  void startXingyun();
}

function startLocalAvatar() {
  void stopXingyun("switch_to_local");
  showAvatarFallback("永久免费本地运行 · 待命", "live");
  addTimeline("本地数字人已启用", "原创程序化形象 · 免费运行 · 星云仅作手动备用", "success");
}

function setupAvatarSource() {
  installHudResponseHook();
  const desktop = Boolean(window.gbtDesktop && window.gbtDesktop.isDesktop);
  if (desktop) {
    document.body.classList.add("is-desktop-shell");
    buildDesktopDock();
    if (typeof window.gbtDesktop.reportScreen === "function") {
      window.gbtDesktop.reportScreen({
        availWidth: window.screen.availWidth,
        availHeight: window.screen.availHeight,
        devicePixelRatio: window.devicePixelRatio || 1,
      });
    }
    if (typeof window.gbtDesktop.onClickThrough === "function") {
      window.gbtDesktop.onClickThrough((active) => {
        toast(active ? "鼠标穿透已开启，Ctrl+Alt+H 可恢复" : "鼠标穿透已关闭", "info");
      });
    }
  }
  const micButton = $("#btn-xy-mic");
  if (micButton) {
    micButton.addEventListener("click", async () => {
      const agent = xingyun.agent;
      if (!agent || xingyun.phase !== "running") {
        toast("星云数字人还没连上，先等她上线", "error");
        return;
      }
      try {
        if (xingyun.micActive) {
          await agent.stopASR();
          setXingyunMic(false);
        } else {
          await agent.startASR();
          setXingyunMic(true);
        }
      } catch (error) {
        setXingyunMic(false);
        toast(`语音识别不可用：${error.message || error}`, "error");
      }
    });
  }
  const localButton = $("#btn-avatar-local");
  const xingyunButton = $("#btn-avatar-xingyun");
  if (localButton) localButton.addEventListener("click", startLocalAvatar);
  if (xingyunButton) xingyunButton.addEventListener("click", startXingyunAvatar);
  if (window.gbtDesktop && typeof window.gbtDesktop.onToggleSource === "function") {
    window.gbtDesktop.onToggleSource(() => {
      if (localAvatar.source === "local") startXingyunAvatar();
      else startLocalAvatar();
    });
  }
  const interruptButton = $("#btn-xy-interrupt");
  if (interruptButton) {
    interruptButton.addEventListener("click", () => {
      const agent = xingyun.agent;
      if (agent && typeof agent.interrupt === "function") {
        try {
          agent.interrupt("speak");
          setXingyunHud("播报已打断", "warn");
        } catch (error) {
          console.warn("[holo_pet] xingyun interrupt failed:", error);
        }
      }
      void interruptCurrentTask();
    });
  }
  const replayButton = $("#btn-xy-replay");
  if (replayButton) {
    replayButton.addEventListener("click", () => {
      if (!xingyun.lastReply) {
        toast("还没有可复读的回复", "info");
        return;
      }
      speakIfEnabled(xingyun.lastReply);
    });
  }
  window.addEventListener("beforeunload", () => {
    const agent = xingyun.agent;
    if (agent && typeof agent.destroy === "function") void agent.destroy("page_unload");
  });
  startLocalAvatar();
}

function buildDesktopDock() {
  const stage = $(".avatar-stage");
  if (!stage || $(".desktop-dock")) return;
  const dock = document.createElement("div");
  dock.className = "desktop-dock";
  const throughButton = document.createElement("button");
  throughButton.type = "button";
  throughButton.textContent = "鼠标穿透";
  throughButton.title = "穿透后鼠标可直接操作下面的窗口，Ctrl+Alt+H 恢复";
  throughButton.addEventListener("click", () => {
    if (window.gbtDesktop && typeof window.gbtDesktop.toggleClickThrough === "function") {
      window.gbtDesktop.toggleClickThrough();
    }
  });
  const panelButton = document.createElement("button");
  panelButton.type = "button";
  panelButton.textContent = "打开面板";
  panelButton.addEventListener("click", () => {
    window.open(`${window.location.origin}/`, "_blank", "noopener");
  });
  const quitButton = document.createElement("button");
  quitButton.type = "button";
  quitButton.textContent = "关闭";
  quitButton.addEventListener("click", () => {
    if (window.gbtDesktop && typeof window.gbtDesktop.quit === "function") {
      window.gbtDesktop.quit();
    }
  });
  dock.append(throughButton, panelButton, quitButton);
  stage.appendChild(dock);
}

async function boot() {
  setupComposer();
  const catalog = await setupCapabilityCatalog();
  await setupObserverAndTree(catalog);
  setupStudio();
  setupBluetooth();
  setupVoiceControls();
  setupSensoryMap();
  setupNotion();
  setupEigenFlux();
  setupDragging();
  refreshState();
  window.setInterval(() => refreshState({ quiet: true }), 30000);
  connectEvents();
  setupAvatarSource();
}

boot();

/* ==================== 社交发布舱区（SOCIAL PUBLISH） ==================== */
app.social = {
  snapshot: null,
  busy: false,
  selected: null,
  pending: null,
  visibility: "private",
};

const SOCIAL_BLOCKED_REASON = "门禁未接通：发布通道暂不可用，先补齐上面的三步前置。";

function setSocialChip(tone, text) {
  const chip = $("#social-state");
  if (!chip) return;
  chip.classList.remove("is-ok", "is-warn", "is-error");
  if (tone === "ok") chip.classList.add("is-ok");
  if (tone === "error") chip.classList.add("is-error");
  const label = chip.querySelector("span");
  if (label) label.textContent = text;
}

function renderSocialGates(gates = []) {
  const host = $("#social-gates");
  if (!host) return;
  const index = {};
  gates.forEach((gate) => { index[gate.id] = gate; });
  $$(".gate-step", host).forEach((step) => {
    const gate = index[step.dataset.gate] || {};
    step.classList.remove("is-ok", "is-missing", "is-unknown", "is-na");
    // 不适用：这条路由不走这道闸。不是"没核验"（未知），更不是"没达标"（红）。
    if (gate.applicable === false) step.classList.add("is-na");
    else if (gate.ok) step.classList.add("is-ok");
    else if (gate.known === false) step.classList.add("is-unknown");
    else step.classList.add("is-missing");
    const hint = step.querySelector("small");
    if (hint && gate.hint) hint.textContent = gate.hint;
  });
}

function describePlatform(platform = {}) {
  if (platform.official_api === false) {
    return platform.audit_gate || "该平台没有官方发布接口，本舱区不做。";
  }
  if (!platform.spec_known) {
    return "本机没有这个平台的规格记录：投递方式与每日上限未知，不猜。";
  }
  const parts = [];
  if (platform.delivery) parts.push(platform.delivery);
  if (platform.daily_limit) parts.push(`每日上限 ${platform.daily_limit} 次`);
  if (platform.audit_gate) parts.push(platform.audit_gate);
  return parts.join(" · ");
}

function renderSocialPlatforms(platforms = [], focusId = "") {
  const host = $("#social-platforms");
  const legacyRail = $("#social-gates");
  if (!host) return;
  const list = Array.isArray(platforms) ? platforms : [];
  host.replaceChildren();
  const active = list.length > 0;
  host.hidden = !active;
  if (legacyRail) legacyRail.hidden = active;
  if (!active) return;

  list.forEach((platform) => {
    const card = document.createElement("article");
    card.className = "platform-card";
    card.dataset.platform = platform.id || "";
    if (platform.id === focusId) card.classList.add("is-focus");

    const head = document.createElement("div");
    head.className = "platform-card__head";
    const name = document.createElement("strong");
    name.textContent = platform.label || platform.id || "未命名平台";
    if (platform.id === focusId) {
      const focusTag = document.createElement("em");
      focusTag.className = "platform-card__focus";
      focusTag.textContent = "当前焦点";
      head.append(name, focusTag);
    } else {
      head.append(name);
    }

    // 探测过期不隐藏卡片、不标红卡片：只把状态降为「待复验」，红色留给摘要区。
    const chip = document.createElement("span");
    chip.className = "platform-chip";
    if (platform.publish_ready) {
      chip.classList.add("is-ok");
      chip.textContent = "可发布";
    } else if (platform.publish_allowed) {
      chip.classList.add("is-warn");
      // 没探过 ≠ 探过又过期：措辞分开，别把"从未探测"说成"待复验"。
      chip.textContent = platform.probe_state === "unprobed" ? "待探测" : "待复验";
    } else {
      chip.classList.add("is-missing");
      chip.textContent = "门禁未接通";
    }
    head.appendChild(chip);

    // 第二枚标记：探针四态。已登记但没探过 -> 「已登记 · 未探测」——
    // 既不是绿（没核验过），也不是「未登记」（登记表里明明有它）。
    if (platform.status_label) {
      const probeChip = document.createElement("span");
      probeChip.className = "platform-chip platform-chip--probe";
      const probeState = platform.probe_state || "unknown";
      if (probeState === "ok") probeChip.classList.add("is-ok");
      else if (probeState === "stale") probeChip.classList.add("is-warn");
      else if (probeState === "failed") probeChip.classList.add("is-missing");
      else probeChip.classList.add("is-unprobed");
      probeChip.textContent = platform.status_label;
      probeChip.title = "探针落点：state/probe/" + (platform.id || "") + ".json";
      head.appendChild(probeChip);
    }

    // 第三枚标记：路由。同一个平台走触手还是走官方接口，门禁的读法完全不同 ——
    // 不印出来，卡片上那几格"不适用"就会被当成"还没做"。
    if (platform.route_label) {
      const routeChip = document.createElement("span");
      routeChip.className = "platform-chip platform-chip--route";
      routeChip.textContent = platform.route_label;
      routeChip.title = platform.route_note || ("路由：" + platform.route_label);
      head.appendChild(routeChip);
    }

    // 第四枚标记：意愿声明。只在登记表**显式**写了 false 时才出现 ——
    // 没写不等于写了 true，所以未声明什么都不印。它不参与门禁计算。
    if (platform.enabled_label) {
      const offChip = document.createElement("span");
      offChip.className = "platform-chip platform-chip--disabled";
      offChip.textContent = platform.enabled_label;
      offChip.title = "登记表声明：本机目前不启用这个渠道。它不参与门禁计算（能不能跑看 blocked_by）。";
      head.appendChild(offChip);
    }

    const specNote = document.createElement("p");
    specNote.className = "platform-card__spec";
    specNote.textContent = describePlatform(platform);

    const rail = document.createElement("ol");
    rail.className = "gate-rail gate-rail--compact";
    (Array.isArray(platform.gates) ? platform.gates : []).forEach((gate) => {
      const step = document.createElement("li");
      step.className = "gate-step";
      step.dataset.gate = gate.id || "";
      // 不适用：不是"没核验"（未知），也不是"没达标"（红）—— 这条路由不走这道闸。
      if (gate.applicable === false) step.classList.add("is-na");
      else if (gate.ok) step.classList.add("is-ok");
      else if (gate.known === false) step.classList.add("is-unknown");
      else step.classList.add("is-missing");

      const mark = document.createElement("span");
      mark.className = "gate-step__mark";
      mark.setAttribute("aria-hidden", "true");
      mark.appendChild(document.createElement("i"));

      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = gate.label || gate.id || "";
      const hint = document.createElement("small");
      hint.textContent = gate.hint || "";
      body.append(title, hint);

      step.append(mark, body);
      rail.appendChild(step);
    });

    card.append(head, specNote, rail);
    host.appendChild(card);
  });
}

function renderSocialDrafts(drafts = []) {
  const host = $("#social-drafts");
  if (!host) return;
  host.replaceChildren();
  if (!drafts.length) {
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = (app.social.snapshot && app.social.snapshot.drafts_ready === false)
      ? "还没有登记成片目录。把要发布的成片放进一个目录，并在 social.json 里登记它，这里就会列出来。"
      : "还没有可发布的成片。先让内核产出成片，再回到这里发布。";
    host.appendChild(note);
    return;
  }
  drafts.forEach((draft) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "draft-card" + (app.social.selected === draft.id ? " is-selected" : "");
    card.dataset.id = draft.id;

    const frame = document.createElement("span");
    frame.className = "draft-card__frame";

    const meta = document.createElement("span");
    meta.className = "draft-card__meta";
    const title = document.createElement("strong");
    title.textContent = draft.name;
    const detail = document.createElement("small");
    detail.textContent = `${draft.size_mb} MB · ${draft.modified}`;
    meta.append(title, detail);

    const state = document.createElement("span");
    state.className = "draft-card__state";
    state.textContent = app.social.selected === draft.id ? "已选中" : "选择";

    card.append(frame, meta, state);
    card.addEventListener("click", () => selectSocialDraft(draft));
    host.appendChild(card);
  });
}

function selectSocialDraft(draft) {
  app.social.selected = draft.id;
  const label = $("#social-target-label");
  if (label) label.textContent = draft.name;
  renderSocialDrafts((app.social.snapshot && app.social.snapshot.drafts) || []);
  syncSocialActions();
}

function renderSocialStream(snapshot = {}) {
  const chip = $("#social-stream-state");
  const facts = $("#social-stream-facts");
  const ffmpeg = snapshot.ffmpeg || {};
  if (chip) {
    chip.classList.remove("is-ok", "is-missing");
    chip.classList.add(ffmpeg.available ? "is-ok" : "is-missing");
    const label = chip.querySelector("span");
    if (label) label.textContent = ffmpeg.available ? "推流工具就绪" : "缺少推流工具";
  }
  if (facts) {
    facts.replaceChildren();
    const rows = [
      ["推流工具", ffmpeg.available ? "已就绪" : "未检测到"],
      ["推流凭据", snapshot.stream_key_ready ? "已登记" : "未登记"],
      ["开播动作", "客户端手动"],
      ["直播事件", snapshot.chat_supported ? "已接通" : "未接通"],
    ];
    rows.forEach(([key, value]) => {
      const row = document.createElement("span");
      const name = document.createElement("i");
      name.textContent = key;
      const state = document.createElement("b");
      state.textContent = value;
      row.append(name, state);
      facts.appendChild(row);
    });
  }
  const button = $("#social-stream-open");
  if (button) button.disabled = !ffmpeg.available || !snapshot.stream_key_ready;
}

function syncSocialActions() {
  const snapshot = app.social.snapshot || {};
  const drafts = snapshot.drafts || [];
  const publishButton = $("#social-publish");
  const pickButton = $("#social-pick");
  const publicInput = $('input[name="social-visibility"][value="public"]');
  const publicLabel = publicInput ? publicInput.closest("label") : null;
  const reason = $("#social-reason");
  const canPublish = Boolean(snapshot.publish_allowed)
    && Boolean(app.social.selected)
    && drafts.length > 0
    && !app.social.busy;

  if (pickButton) pickButton.disabled = drafts.length === 0;
  if (publicInput) publicInput.disabled = !snapshot.public_allowed;
  if (publicLabel) publicLabel.classList.toggle("is-locked", !snapshot.public_allowed);
  if (publishButton) publishButton.disabled = !canPublish;

  if (reason) {
    const notes = [];
    if (!snapshot.publish_allowed) notes.push(snapshot.blocked_reason || SOCIAL_BLOCKED_REASON);
    if (!drafts.length) notes.push("还没有可选的成片。");
    else if (!app.social.selected) notes.push("先选中一条成片。");
    if (snapshot.route_label) {
      notes.push("无人值守未启用：这一下需要人在场。");
    } else if (!snapshot.public_allowed) {
      notes.push("公开可见需要权限过审；未过审只能走私密。");
    }
    reason.textContent = canPublish
      ? "门禁已接通，发布前会再要你确认一次。"
      : notes.join(" ");
    reason.classList.toggle("is-blocked", !canPublish);
  }

  renderSocialStream(snapshot);
}

function applySocialSnapshot(payload = {}) {
  app.social.snapshot = payload;
  const drafts = Array.isArray(payload.drafts) ? payload.drafts : [];
  if (!drafts.some((draft) => draft.id === app.social.selected)) {
    app.social.selected = drafts.length ? drafts[0].id : null;
  }
  const picked = drafts.find((draft) => draft.id === app.social.selected);
  const label = $("#social-target-label");
  if (label) label.textContent = picked ? picked.name : "未选择成片";

  const summary = $("#social-summary");
  const ready = (payload.gates || []).filter((gate) => gate.ok).length;
  const probe = payload.capability_probe || {};
  if (summary) {
    const prefix = payload.focus_label ? `${payload.focus_label} · ` : "";
    let tail = "发布通道未接通";
    if (payload.publish_ready) tail = "全部门禁已接通，公开可见已解锁";
    else if (probe.status === "stale") tail = "探测过期，需复验后才能发布";
    else if (payload.publish_allowed) tail = "凭据或能力尚未核验";
    if (payload.route_label) {
      // 触手路由下官方三步闸不适用，印"0/3 已就绪"会被读成"一件事都没做"。
      summary.textContent = `${prefix}${payload.route_label}路由 · ${tail}`;
    } else {
      summary.textContent = `${prefix}门禁 ${ready}/3 已就绪 · ${tail}`;
    }
    // 只有摘要区标红：卡片照常显示"待复验"，不对过期做卡片级封杀。
    summary.classList.toggle("is-blocked", !payload.publish_ready);
  }
  setSocialChip(payload.connected ? "ok" : "warn", payload.connected ? "门禁已接通" : "门禁未接通");
  renderSocialGates(payload.gates || []);
  renderSocialPlatforms(payload.platforms || [], payload.focus || "");
  renderSocialDrafts(drafts);
  syncSocialActions();
}

async function refreshSocial({ quiet = false } = {}) {
  if (app.social.busy) return;
  app.social.busy = true;
  if (!quiet) setSocialChip("warn", "门禁检查中");
  try {
    const payload = await postJson("/api/social", { op: "status" });
    applySocialSnapshot(payload);
  } catch (error) {
    setSocialChip("error", "门禁读取失败");
    const summary = $("#social-summary");
    if (summary) {
      summary.textContent = "读取发布门禁失败：" + safeLastErrorOr(
        String((error && error.message) || error), "面板未响应");
    }
    syncSocialActions();
  } finally {
    app.social.busy = false;
  }
}

function requestSocialPublish() {
  const drafts = (app.social.snapshot && app.social.snapshot.drafts) || [];
  const draft = drafts.find((item) => item.id === app.social.selected);
  if (!draft) {
    toast("先选中一条成片", "error", 2600);
    return;
  }
  app.social.pending = { draft, visibility: app.social.visibility };
  const summary = $("#social-confirm-summary");
  if (summary) {
    const snapshot = app.social.snapshot || {};
    const target = snapshot.focus_label ? `${snapshot.focus_label} · ` : "";
    summary.textContent = `${target}${draft.name} · ${
      app.social.visibility === "public" ? "公开可见" : "私密可见"}`;
  }
  const box = $("#social-confirm");
  if (box) box.hidden = false;
}

async function confirmSocialPublish() {
  const pending = app.social.pending;
  if (!pending) return;
  const box = $("#social-confirm");
  if (box) box.hidden = true;
  app.social.busy = true;
  syncSocialActions();
  let handled = false;
  try {
    const snapshot = app.social.snapshot || {};
    const result = await postJson("/api/social", {
      op: "publish",
      // 显式带上焦点平台：服务端只认声明过的平台，且多平台时不做替选。
      platform: snapshot.focus || "",
      draft: pending.draft.id,
      visibility: pending.visibility,
    });
    handled = Boolean(result && result.ok);
    const detail = (result && (result.detail || result.error)) || SOCIAL_BLOCKED_REASON;
    toast(detail, handled ? "success" : "error", handleTimeout(detail));
    addTimeline("社交发布", detail, "system");
  } catch (error) {
    const detail = safeLastErrorOr(String((error && error.message) || error), SOCIAL_BLOCKED_REASON);
    toast(detail, "error");
    addTimeline("社交发布", detail, "system");
  } finally {
    app.social.busy = false;
    app.social.pending = null;
    await refreshSocial({ quiet: true });
  }
  return handled;
}

function handleTimeout(text) {
  return String(text || "").length > 40 ? 5200 : 3200;
}

function setupSocial() {
  const refresh = $("#social-refresh");
  if (refresh) refresh.addEventListener("click", () => refreshSocial());
  const publishButton = $("#social-publish");
  if (publishButton) publishButton.addEventListener("click", requestSocialPublish);
  const pickButton = $("#social-pick");
  if (pickButton) {
    pickButton.addEventListener("click", () => {
      const drafts = (app.social.snapshot && app.social.snapshot.drafts) || [];
      if (!drafts.length) {
        toast("还没有可选的成片", "error", 2600);
        return;
      }
      const at = drafts.findIndex((draft) => draft.id === app.social.selected);
      selectSocialDraft(drafts[(at + 1) % drafts.length]);
    });
  }
  const confirmYes = $("#social-confirm-yes");
  if (confirmYes) confirmYes.addEventListener("click", confirmSocialPublish);
  const confirmCancel = $("#social-confirm-cancel");
  if (confirmCancel) {
    confirmCancel.addEventListener("click", () => {
      app.social.pending = null;
      const box = $("#social-confirm");
      if (box) box.hidden = true;
    });
  }
  $$('input[name="social-visibility"]').forEach((input) => {
    input.addEventListener("change", () => {
      if (!input.checked) return;
      app.social.visibility = input.value;
      $$('input[name="social-visibility"]').forEach((other) => {
        const label = other.closest("label");
        if (label) label.classList.toggle("is-on", other.checked);
      });
      syncSocialActions();
    });
  });
  const streamButton = $("#social-stream-open");
  if (streamButton) {
    streamButton.addEventListener("click", () => {
      toast("推流要先在客户端自助拿到推流地址与凭据，登记后才能在这里启动。", "error", 4600);
    });
  }
  syncSocialActions();
  refreshSocial({ quiet: true });
}

setupSocial();

/* ==================== 调研信源舱区（RESEARCH SOURCES） ==================== */
app.research = {
  snapshot: null,
  busy: false,
};

// 采集六态 -> 卡片色阶。口诀：『没采过』(中性蓝灰) 与 『采集失败』(红) 必须一眼分得开 ——
// 前者不是故障，后者是。『未启用』是登记表的意愿声明，也不是错。
const RESEARCH_CHIP_CLASS = {
  ok: "is-ok",
  failed: "is-missing",
  unreadable: "is-unreadable",
  stale: "is-stale",
  never_run: "is-never-run",
  disabled: "platform-chip--disabled",
};

function setResearchChip(tone, text) {
  const chip = $("#research-state");
  if (!chip) return;
  chip.classList.remove("is-ok", "is-warn", "is-error");
  if (tone === "ok") chip.classList.add("is-ok");
  if (tone === "error") chip.classList.add("is-error");
  const label = chip.querySelector("span");
  if (label) label.textContent = text;
}

function describeResearchSource(source = {}) {
  const parts = [];
  if (source.kind) parts.push(source.kind);
  if (source.interval) parts.push(source.interval === "weekly" ? "每周采集" : "每日采集");
  else if (source.interval_known === false) parts.push("采集周期未登记（按日度判定）");
  if (source.endpoint) parts.push(source.endpoint);
  if (!parts.length) parts.push(source.note || "登记表里没有更多描述。");
  return parts.join(" · ");
}

function renderResearchSources(sources = []) {
  const host = $("#research-sources-list");
  if (!host) return;
  const list = Array.isArray(sources) ? sources : [];
  host.replaceChildren();
  host.hidden = list.length === 0;
  if (!list.length) return;

  list.forEach((source) => {
    const card = document.createElement("article");
    card.className = "platform-card";
    card.dataset.source = source.id || "";

    const head = document.createElement("div");
    head.className = "platform-card__head";
    const name = document.createElement("strong");
    name.textContent = source.name || source.id || "未命名信源";
    head.appendChild(name);

    // 第一枚：采集态，这张卡的主结论。
    const chip = document.createElement("span");
    const state = source.state || "";
    chip.className = "platform-chip " + (RESEARCH_CHIP_CLASS[state] || "is-unprobed");
    chip.textContent = source.status_label || state || "状态未知";
    chip.title = source.hint || "";
    head.appendChild(chip);

    // 第二枚：意愿声明，只在登记表**显式**写 false 时出现（没写不等于写了 true）。
    if (source.enabled_label) {
      const off = document.createElement("span");
      off.className = "platform-chip platform-chip--disabled";
      off.textContent = source.enabled_label;
      off.title = "登记表声明：本机目前不采集这个源。它不是采集失败。";
      head.appendChild(off);
    }

    // 第三枚：采集周期。没登记也如实印出来，别让它偷偷按日度算。
    if (source.interval || source.interval_known === false) {
      const span = document.createElement("span");
      span.className = "platform-chip platform-chip--interval";
      span.textContent = source.interval
        ? (source.interval === "weekly" ? "周度" : "日度")
        : "周期未登记";
      head.appendChild(span);
    }

    const spec = document.createElement("p");
    spec.className = "platform-card__spec";
    spec.textContent = describeResearchSource(source);

    // 判据 E：该源标红。卡片本身也红 —— 只靠一枚小标记不够显眼。
    if (source.severity === "red") card.classList.add("is-severity-red");

    const detail = document.createElement("p");
    detail.className = "platform-card__spec";
    detail.textContent = source.hint || "";

    // 判据 E 的另一半：本次值 / 历史水位**分两格**印。
    // 本次没采到就写「没有本次记录」，绝不把历史条数挪到本次那一格。
    const thisRun = source.this_run || {};
    const history = source.history || {};
    const values = document.createElement("p");
    values.className = "platform-card__values";

    const nowCell = document.createElement("span");
    const nowLabel = document.createElement("b");
    nowLabel.textContent = "本次";
    const nowItems = (typeof thisRun.items === "number") ? (thisRun.items + " 条") : "条数未知";
    let nowText;
    if (!thisRun.present) {
      nowText = "没有本次记录（未采到）—— 不是 0，也不是上次的值";
    } else {
      const outcome = thisRun.outcome === "ok" ? "成功"
        : (thisRun.outcome === "failed" ? "失败" : "未记结局");
      nowText = outcome + (thisRun.http ? " · HTTP " + thisRun.http : "") + " · " + nowItems;
    }
    nowCell.append(nowLabel, document.createTextNode(" " + nowText));

    const pastCell = document.createElement("span");
    pastCell.className = "is-history";
    const pastLabel = document.createElement("b");
    pastLabel.textContent = "历史（上一次成功）";
    const pastText = history.watermark_age_label
      ? history.watermark_age_label + "前"
        + (typeof history.items === "number" ? "（当时 " + history.items + " 条）" : "")
      : "无水位";
    pastCell.append(pastLabel, document.createTextNode(" " + pastText));

    values.append(nowCell, pastCell);
    if (thisRun.present && thisRun.reason) {
      const why = document.createElement("span");
      why.textContent = "失败原因：" + String(thisRun.reason).slice(0, 160);
      values.append(why);
    }

    card.append(head, spec, detail, values);
    host.appendChild(card);
  });
}

function applyResearchSnapshot(payload = {}) {
  app.research.snapshot = payload;
  const summary = $("#research-summary");
  renderResearchSources(payload.sources);
  const report = payload.run_report || {};
  if (summary) {
    const parts = [payload.summary || "本机读不到调研信源的登记表。"];
    if (report.red_count) {
      parts.push("标红：" + (report.failed_sources || []).join("、"));
    }
    if (typeof report.this_run_items_total === "number") {
      parts.push("本次共 " + report.this_run_items_total + " 条 / "
        + report.this_run_sources_counted + " 个源成功入库");
    } else {
      parts.push("本次还没有任何源成功入库");
    }
    summary.textContent = parts.join(" · ");
  }
  // 色阶只认判据 E 的 severity：没采过与未启用都不该把标题染红。
  if (report.severity === "red" || payload.failed_count || payload.unreadable_count) {
    setResearchChip("error", (payload.failed_count || 0) + " 个采集失败");
  } else if (!payload.sources_verified) {
    setResearchChip("warn", "登记表不可信");
  } else if (payload.ok_count) {
    setResearchChip("ok", "有可用水位");
  } else {
    setResearchChip("warn", "还没有采集记录");
  }
}

async function refreshResearch({ quiet = false } = {}) {
  if (app.research.busy) return;
  app.research.busy = true;
  if (!quiet) setResearchChip("warn", "读取中");
  try {
    applyResearchSnapshot(await postJson("/api/research", { op: "status" }));
  } catch (error) {
    setResearchChip("error", "读取失败");
    const summary = $("#research-summary");
    if (summary) summary.textContent = "本机读不到调研信源状态。";
  } finally {
    app.research.busy = false;
  }
}

function setupResearch() {
  const refresh = $("#research-refresh");
  if (refresh) refresh.addEventListener("click", () => refreshResearch());
  refreshResearch({ quiet: true });
}

setupResearch();
