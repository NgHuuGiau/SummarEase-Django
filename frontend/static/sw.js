// Service Worker for SummarEase PWA
// Version: 20260909-1

const CACHE_NAME = 'summarease-v20260909-1';
const STATIC_CACHE = 'summarease-static-v20260909-1';
const DYNAMIC_CACHE = 'summarease-dynamic-v20260909-1';

// Files to cache on install
const STATIC_ASSETS = [
  '/',
  '/static/css/tokens-base.css',
  '/static/css/layout-buttons.css',
  '/static/css/form-area.css',
  '/static/css/history.css',
  '/static/css/pages-footer.css',
  '/static/css/responsive.css',
  '/static/js/app.js',
  '/static/manifest.json',
];

// Cache strategies
const CACHE_STRATEGIES = {
  // Static assets: cache first
  'static': async (request, cache) => {
    const cached = await cache.match(request);
    if (cached) return cached;
    try {
      const response = await fetch(request);
      if (response.ok) cache.put(request, response.clone());
      return response;
    } catch {
      return new Response('Offline', { status: 503 });
    }
  },

  // API calls: network first, fallback to cache
  'api': async (request, cache) => {
    try {
      const response = await fetch(request);
      if (response.ok) cache.put(request, response.clone());
      return response;
    } catch {
      const cached = await cache.match(request);
      return cached || new Response(JSON.stringify({ error: 'Offline' }), {
        headers: { 'Content-Type': 'application/json' },
        status: 503,
      });
    }
  },

  // HTML pages: network first with offline fallback
  'html': async (request, cache) => {
    try {
      const response = await fetch(request);
      if (response.ok) cache.put(request, response.clone());
      return response;
    } catch {
      const cached = await cache.match('/');
      return cached || new Response('Offline', { status: 503 });
    }
  },
};

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== DYNAMIC_CACHE)
          .map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Skip chrome-extension and other non-http(s) schemes
  if (!url.protocol.startsWith('http')) return;

  let cacheName;
  let strategy;

  if (STATIC_ASSETS.some((asset) => url.pathname.startsWith(asset))) {
    cacheName = STATIC_CACHE;
    strategy = CACHE_STRATEGIES.static;
  } else if (url.pathname.startsWith('/api/')) {
    cacheName = DYNAMIC_CACHE;
    strategy = CACHE_STRATEGIES.api;
  } else if (
    url.pathname === '/' ||
    url.pathname.startsWith('/history') ||
    url.pathname.startsWith('/settings') ||
    url.pathname.startsWith('/login') ||
    url.pathname.startsWith('/register')
  ) {
    cacheName = DYNAMIC_CACHE;
    strategy = CACHE_STRATEGIES.html;
  } else {
    // Default: network first
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.open(cacheName).then((cache) => strategy(event.request, cache))
  );
});

// Handle background sync for offline form submissions
self.addEventListener('sync', (event) => {
  if (event.tag === 'summary-submit') {
    event.waitUntil(syncSummaries());
  }
});

async function syncSummaries() {
  const db = await openDB();
  const pending = await db.getAll('pendingSummaries');
  
  for (const item of pending) {
    try {
      const response = await fetch('/api/v1/summaries/create/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(item.data),
      });
      
      if (response.ok) {
        await db.delete('pendingSummaries', item.id);
      }
    } catch {
      // Will retry on next sync
    }
  }
}

// Simple IndexedDB wrapper
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('SummarEaseDB', 1);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pendingSummaries')) {
        db.createObjectStore('pendingSummaries', { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Listen for messages from main thread
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});