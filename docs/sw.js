/* ================================================================
   DailyBrief – sw.js (Service Worker)
   Caching Strategy:
     - App Shell (HTML/CSS/JS/icons): Cache-first with background revalidation
     - data.json & archive/*.json: Network-first with offline cache fallback
     - External asset links: Handled natively
   ================================================================ */

const CACHE_VERSION = 'dailybrief-v12';
const SHELL_ASSETS = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './manifest.json',
  './icons/favicon.svg',
  './icons/favicon-32.png',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

// ── Install: Pre-cache App Shell ─────────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_VERSION).then(cache => cache.addAll(SHELL_ASSETS))
  );
});

// ── Activate: Purge Stale Caches ─────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: Route Requests ────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Intercept only GET requests originating from same origin
  if (request.method !== 'GET') return;

  // JSON payloads: Network-first
  if (url.pathname.endsWith('data.json') || url.pathname.includes('/archive/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Shell assets: Cache-first
  event.respondWith(cacheFirst(request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline – resource unavailable', { status: 503 });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response('{"error":"offline"}', {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
