const STATIC_ASSETS = [
  '/',
  '/styles.css',
  '/logo.png',
  '/manifest.json',
  '/js/app-main.js',
  '/js/app-auth-init.js',
  '/js/app-activities-ops.js',
  '/js/app-editor-upload.js',
  '/js/app-site-editor-core.js',
];
const SW_VERSION = '20260314a';
const SCRIPT_URL = new URL(self.location.href);
const CACHE_VERSION = SCRIPT_URL.searchParams.get('v') || SW_VERSION;
const CACHE_NAME = `weave-static-${CACHE_VERSION}`;
let REDUCED_DATA_MODE = false;
const API_NON_CACHEABLE_PREFIXES = ['/api/auth', '/api/admin', '/api/me', '/api/users'];

self.addEventListener('message', (event) => {
  const payload = event && event.data ? event.data : {};
  if (payload.type === 'WEAVE_REDUCED_DATA_MODE') {
    REDUCED_DATA_MODE = !!payload.enabled;
  }
});

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => Promise.resolve())
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== 'GET') return;

  const isApi = url.pathname.startsWith('/api/');
  if (isApi) {
    const nonCacheable = API_NON_CACHEABLE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (!nonCacheable && req.method === 'GET' && res.ok && !REDUCED_DATA_MODE) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => new Response(JSON.stringify({ error: 'offline' }), { status: 503, headers: { 'Content-Type': 'application/json' } }))
    );
    return;
  }

  if (url.pathname === '/sw.js') {
    return;
  }

  const isStatic = /\.(?:css|js|png|jpg|jpeg|webp|gif|svg|ico)$/.test(url.pathname) || STATIC_ASSETS.includes(url.pathname);
  if (isStatic) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          if (!REDUCED_DATA_MODE) {
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('/')))
    );
  }
});
