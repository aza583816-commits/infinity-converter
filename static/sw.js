const CACHE = 'infinity-static-v7.2.1';
const STATIC_ASSETS = [
  '/static/css/app.css?v=7.2.1',
  '/static/js/app.js?v=7.2.1',
  '/static/icon-192.png?v=7.2.1',
  '/static/icon-512.png?v=7.2.1',
  '/manifest.json?v=7.2.1'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => undefined));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith('infinity-static-') && key !== CACHE).map((key) => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const cacheable = url.pathname.startsWith('/static/') || url.pathname === '/manifest.json';
  if (!cacheable) return;
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) caches.open(CACHE).then((cache) => cache.put(request, response.clone())).catch(() => {});
      return response;
    }))
  );
});
