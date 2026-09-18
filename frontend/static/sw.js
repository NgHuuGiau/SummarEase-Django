// Cache only public static assets. Never persist authenticated HTML or API data.
const STATIC_CACHE = 'summarease-static-v20260918-1';
const STATIC_ASSETS = [
  '/static/css/tokens-base.css',
  '/static/css/layout-buttons.css',
  '/static/css/form-area.css',
  '/static/css/history.css',
  '/static/css/pages-footer.css',
  '/static/css/responsive.css',
  '/static/js/app.js',
  '/static/manifest.json',
  '/static/icons/summarease.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(keys.filter((key) => key.startsWith('summarease-') && key !== STATIC_CACHE)
        .map((key) => caches.delete(key)));
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;

  if (!STATIC_ASSETS.includes(url.pathname)) {
    return;
  }

  event.respondWith(
    caches.open(STATIC_CACHE).then(async (cache) => {
      const cached = await cache.match(event.request);
      if (cached) return cached;
      const response = await fetch(event.request);
      if (response.ok) await cache.put(event.request, response.clone());
      return response;
    })
  );
});

// Listen for messages from main thread
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
