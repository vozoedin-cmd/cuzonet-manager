const CACHE_NAME = 'cuzonet-cache-v1';
const ASSETS = [
  '/login',
  '/static/css/style.css',
  '/static/img/logo.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS).catch(err => console.log("SW Install cache warning:", err));
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Strategy: Network First with cache fallback
  if (e.request.method === 'GET') {
    e.respondWith(
      fetch(e.request).catch(() => {
        return caches.match(e.request);
      })
    );
  }
});
