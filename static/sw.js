const CACHE_NAME = 'xuxiaoxiong-v1';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/avatar.jpg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // 跳过 API / 聊天 / 记忆写入 — 永远走网络
  if (
    url.pathname.startsWith('/chat') ||
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/remember')
  ) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request)
        .then((response) => {
          if (response && response.status === 200 && event.request.method === 'GET') {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(() => {
          // 离线时返回缓存页面
          return cached || new Response('离线中，稍后再来哦 OvO', { status: 503 });
        });
      return cached || fetchPromise;
    })
  );
});
