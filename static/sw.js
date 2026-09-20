// Network-first stylesheets prevent a stale/partial cached CSS response from
// leaving the entire site unstyled after a deployment. Never cache opaque HTML
// fallbacks as CSS, and never allow service-worker cache failure to block CSS.
const CACHE = 'infinity-static-v8.0.0-css-recovery-20260920';
const STATIC_ASSETS = [
  '/static/js/app.js?v=8.0.0',
  '/static/js/smart-flow.js?v=8.0.0',
  '/static/js/workflows.js?v=8.0.0',
  '/static/js/workspace.js?v=8.0.0',
  '/static/js/trust-badges.js?v=8.0.0',
  '/static/js/vitals.js?v=8.0.0',
  '/static/icon-192.png?v=8.0.0',
  '/static/icon-512.png?v=8.0.0',
  '/manifest.json?v=8.0.0'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => undefined));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key.startsWith('infinity-static-') && key !== CACHE)
      .map((key) => caches.delete(key))
  )));
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // CSS must never be silently served from a stale cache. Request it directly
  // so a failure remains visible to the browser and monitoring.
  if (url.pathname.startsWith('/static/css/') && url.pathname.endsWith('.css')) {
    event.respondWith(fetch(request, {cache: 'no-store'}));
    return;
  }

  const cacheable = url.pathname.startsWith('/static/') || url.pathname === '/manifest.json';
  if (!cacheable) return;
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok && response.type !== 'opaque') {
        caches.open(CACHE).then((cache) => cache.put(request, response.clone())).catch(() => {});
      }
      return response;
    }))
  );
});
