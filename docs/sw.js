/* ================================================================
   DailyBrief – sw.js  (Service Worker)
   Estratégia:
     - App shell (HTML/CSS/JS): Cache-first, atualiza em background
     - data.json: Network-first, fallback para cache
     - Imagens / ícones: Cache-first
   ================================================================ */

const CACHE_VERSION = 'dailybrief-v1';
const SHELL_ASSETS = [
  './',
  './index.html',
  './style.css',
  './app.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

// ── Instalação: pré-cache do shell ──────────────────────────────
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_VERSION).then(cache => cache.addAll(SHELL_ASSETS))
  );
});

// ── Ativação: limpa caches antigos ─────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: roteamento de cache ──────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Apenas GET e mesma origem (ou CDN confiável)
  if (request.method !== 'GET') return;

  // data.json e arquivos: Network-first
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
    return new Response('Offline – recurso não disponível', { status: 503 });
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
