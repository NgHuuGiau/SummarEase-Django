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
  // Cache each asset independently: one slow/missing file must not fail
  // the whole install (a single addAll rejection discards the worker and
  // leaves behind an empty cache under this same name).
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) =>
      Promise.all(
        STATIC_ASSETS.map((url) => cache.add(url).catch(() => undefined))
      )
    )
  );
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
      // Match/put by origin+pathname: pages request versioned URLs (?v=...),
      // the cache stores a single copy per asset.
      const cacheKey = url.origin + url.pathname;
      const cached = await cache.match(cacheKey);
      if (cached) return cached;
      const response = await fetch(event.request);
      if (response.ok) await cache.put(cacheKey, response.clone());
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
