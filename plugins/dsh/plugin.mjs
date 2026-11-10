// @gbt/dsh-cap-bridge
// DSH 插件统一入口：把 GBT小土豆V8 的 428 个能力位暴露成三个 DSH 工具。
//
// 设计口径（主人 2026-11-10）：「别动她的环境，把插件统一入口就好了」。
//   · 本包是**独立插件**：只读她 profile 的公开 SDK，不 import 她的内部模块；
//   · 安装/卸载都走 DSH 自己的 `dpx plugin add/remove`，不手改 profile；
//   · 所有副作用都在本桥后面：只读能力直接执行，改状态的能力必须 `confirm: true`；
//   · 桥默认只绑 127.0.0.1，且要求本地令牌（`state/dsh-plugin/bridge-token`）。
import { defineTool } from "@deepseek-ai/dsh-tools";

const name = "gbt-cap-bridge";
const inject = ["tools", "agents"];

const DEFAULT_ENDPOINT = "http://127.0.0.1:8790";

function resolveEndpoint(config) {
	const raw = (config && config.endpoint) || process.env.GBT_DSH_BRIDGE || DEFAULT_ENDPOINT;
	return String(raw).replace(/\/+$/, "");
}

function resolveToken(config) {
	return String((config && config.token) || process.env.GBT_DSH_BRIDGE_TOKEN || "");
}

async function request(config, path, init) {
	const headers = {
		"content-type": "application/json",
		...(resolveToken(config) ? { "x-gbt-token": resolveToken(config) } : {}),
		...(init && init.headers ? init.headers : {})
	};
	let response;
	try {
		response = await fetch(resolveEndpoint(config) + path, {
			...init,
			headers,
			signal: AbortSignal.timeout(120000)
		});
	} catch (error) {
		throw new Error(
			"GBT 桥不可达（" + resolveEndpoint(config) + "）：" + ((error && error.message) || error) +
			"。先在 GBT 仓启动：.\\pyembed\\python.exe plugins\\dsh\\bridge\\gbt_bridge.py"
		);
	}
	const text = await response.text();
	let body;
	try {
		body = JSON.parse(text);
	} catch {
		body = { ok: false, error: text.slice(0, 400) };
	}
	if (!response.ok) {
		throw new Error("GBT 桥 HTTP " + response.status + "：" + (body.error || text.slice(0, 200)));
	}
	return body;
}

const jsonOutput = {
	schema: { type: "json" },
	render: (_args, value) => [{ type: "text", text: JSON.stringify(value, null, 2) }]
};

function capsTool(config) {
	return defineTool({
		name: "gbt_caps",
		description: "列出 GBT小土豆V8 的能力位（只读）。先用它查名字，再调 gbt_cap。",
		parameters: {
			domain: { type: "string", description: "按域过滤，如 llm / vision / fs / system。" },
			keyword: { type: "string", description: "按能力名或描述搜关键字。" },
			limit: { type: "integer", description: "最多返回条数，默认 60。" },
			detail: { type: "boolean", description: "true 时带 domain 与 desc。" }
		},
		output: jsonOutput,
		async execute(args) {
			const query = new URLSearchParams();
			if (args.domain) query.set("domain", args.domain);
			if (args.keyword) query.set("keyword", args.keyword);
			if (args.limit) query.set("limit", String(args.limit));
			if (args.detail) query.set("detail", "1");
			const suffix = query.toString() ? "?" + query.toString() : "";
			return request(config, "/caps" + suffix, { method: "GET" });
		}
	});
}

function capTool(config) {
	return defineTool({
		name: "gbt_cap",
		description:
			"调用一个 GBT 能力位。只读能力直接执行；改状态的能力必须显式 confirm=true，" +
			"否则桥会返回 need_confirm 并说明缺什么。",
		parameters: {
			kind: { type: "string", required: true, description: "能力位名，如 cloud_llm / gbt_health。" },
			payload: { type: "json", description: "给该能力位的入参对象（默认 {}）。" },
			confirm: {
				type: "boolean",
				description: "改状态时必须为 true；只读能力不需要。"
			}
		},
		output: jsonOutput,
		async execute(args) {
			return request(config, "/run", {
				method: "POST",
				body: JSON.stringify({
					kind: args.kind,
					payload: args.payload ?? {},
					confirm: args.confirm === true
				})
			});
		}
	});
}

function healthTool(config) {
	return defineTool({
		name: "gbt_health",
		description: "GBT 桥健康读数：是否在线、能力位总数、版本、令牌文件位置。",
		parameters: {},
		output: jsonOutput,
		async execute() {
			return request(config, "/health", { method: "GET" });
		}
	});
}

function install(agent, config) {
	const scoped = agent.ctx;
	const disposers = [capsTool(config), capTool(config), healthTool(config)]
		.map((tool) => scoped.tools.register(tool));
	return () => {
		for (const dispose of disposers.reverse()) dispose();
	};
}

function apply(ctx, config = {}) {
	const installed = new Map();
	const maybeInstall = (agent) => {
		if (installed.has(agent)) return;
		installed.set(agent, install(agent, config));
	};
	for (const agent of ctx.agents.list()) maybeInstall(agent);
	ctx.on("agent/created", ({ agent }) => maybeInstall(agent));
	ctx.on("agent/disposed", ({ agent }) => {
		const dispose = installed.get(agent);
		if (dispose) dispose();
		installed.delete(agent);
	});
	ctx.effect(() => () => {
		for (const dispose of installed.values()) dispose();
		installed.clear();
	}, "gbt-cap-bridge.scopedTools()");
}

export { apply, inject, name };
