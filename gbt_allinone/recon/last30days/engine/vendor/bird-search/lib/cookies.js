// ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
/**
 * cookies.js —— GBT小土豆V8 同化改写件（2026-09-18 供应链审查）
 *
 * 上游此文件会把读取本机浏览器 cookie 的活（Safari / Chrome / Firefox，
 * 经 npm 包 @steipete/sweet-cookie）委派出去，用来"零配置"拿到 X 的
 * auth_token / ct0。按 GBT小土豆V8 供应链红线，**浏览器读取通道整块拆除**：
 * 本文件只从环境变量解析凭据，不再 import 任何 cookie 读取依赖，
 * 也不再触碰本机浏览器数据库。
 *
 * 保留的导出与原版一致（bird-search.mjs 只用 resolveCredentials）：
 *   resolveCredentials(options) -> { cookies, warnings }
 *   extractCookiesFromSafari/Chrome/Firefox -> 显式禁用桩（调用即报错）
 *
 * 凭据来源（按优先级）：
 *   1. options.authToken / options.ct0（CLI 参数）
 *   2. 环境变量 AUTH_TOKEN / TWITTER_AUTH_TOKEN、CT0 / TWITTER_CT0
 * 拿不到就如实返回 warnings —— 不伪造、不静默降级。
 */

const TWITTER_COOKIE_NAMES = ['auth_token', 'ct0'];
const DISABLED_MSG =
    '浏览器 cookie 读取已在 GBT小土豆V8 同化时移除：请改用 AUTH_TOKEN / CT0 环境变量显式提供。';

function normalizeValue(value) {
    if (typeof value !== 'string') {
        return null;
    }
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
}

function cookieHeader(authToken, ct0) {
    return `auth_token=${authToken}; ct0=${ct0}`;
}

function buildEmpty() {
    return { authToken: null, ct0: null, cookieHeader: null, source: null };
}

function readEnvCookie(cookies, keys, field) {
    if (cookies[field]) {
        return;
    }
    for (const key of keys) {
        const value = normalizeValue(process.env[key]);
        if (!value) {
            continue;
        }
        cookies[field] = value;
        if (!cookies.source) {
            cookies.source = `env ${key}`;
        }
        break;
    }
}

async function disabledStub(name) {
    throw new Error(`${name}: ${DISABLED_MSG}`);
}

export async function extractCookiesFromSafari() {
    return disabledStub('extractCookiesFromSafari');
}

export async function extractCookiesFromChrome(_profile) {
    return disabledStub('extractCookiesFromChrome');
}

export async function extractCookiesFromFirefox(_profile) {
    return disabledStub('extractCookiesFromFirefox');
}

/**
 * Resolve Twitter credentials —— 只认显式来源（CLI 参数 > 环境变量）。
 */
export async function resolveCredentials(options) {
    const opt = options || {};
    const warnings = [];
    const cookies = buildEmpty();

    if (opt.authToken) {
        cookies.authToken = opt.authToken;
        cookies.source = 'CLI argument';
    }
    if (opt.ct0) {
        cookies.ct0 = opt.ct0;
        if (!cookies.source) {
            cookies.source = 'CLI argument';
        }
    }

    readEnvCookie(cookies, ['AUTH_TOKEN', 'TWITTER_AUTH_TOKEN'], 'authToken');
    readEnvCookie(cookies, ['CT0', 'TWITTER_CT0'], 'ct0');

    if (cookies.authToken && cookies.ct0) {
        cookies.cookieHeader = cookieHeader(cookies.authToken, cookies.ct0);
        return { cookies, warnings };
    }

    if (!cookies.authToken) {
        warnings.push(
            'Missing auth_token - provide via --auth-token or the AUTH_TOKEN env var. ' +
            DISABLED_MSG
        );
    }
    if (!cookies.ct0) {
        warnings.push(
            'Missing ct0 - provide via --ct0 or the CT0 env var. ' + DISABLED_MSG
        );
    }
    return { cookies, warnings };
}
