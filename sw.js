/* GBT小土豆V8 · 最小 Service Worker
 * 目的：让 iPhone「添加到主屏幕」/ Android「安装应用」之后**离线也能打开**落地页与 2 万触手 3D 页。
 * 策略（写死，不玩花活）：
 *   · 导航请求（HTML）：network-first，网断了退回缓存（保证内容能更新，但不至于白屏）
 *   · 静态资源（png/svg/gif/webmanifest）：cache-first（省流量、打开快）
 *   · 只缓存**同源 GET**，别碰能力位 API（这里没有 API，别以后误加）
 */
const VERSION = 'gbt-v8-v2';
const SHELL = [
  './',
  './index.html',
  './manifest.webmanifest',
  './arms/tentacle3d.html',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png',
  './assets/fig-caps.png',
  './assets/fig-cable-all.png',
  './assets/social-preview.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(VERSION).then((c) => Promise.all(
      SHELL.map((u) => c.add(u).catch(() => null))   // 单个失败不拖垮整体
    )).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  const isHtml = req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');
  if (isHtml) {
    e.respondWith(
      fetch(req).then((resp) => {
        const copy = resp.clone();
        caches.open(VERSION).then((c) => c.put(req, copy));
        return resp;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match('./index.html')))
    );
    return;
  }
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((resp) => {
      const copy = resp.clone();
      caches.open(VERSION).then((c) => c.put(req, copy));
      return resp;
    }).catch(() => hit))
  );
});
