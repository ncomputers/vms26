importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js');

workbox.setConfig({ debug: false });
workbox.core.clientsClaim();

workbox.precaching.precacheAndRoute(self.__WB_MANIFEST);

workbox.routing.registerRoute(
  ({url, request}) => url.pathname.startsWith('/api/') && request.method === 'GET',
  new workbox.strategies.StaleWhileRevalidate({
    cacheName: 'api-cache-v1'
  })
);

workbox.routing.registerRoute(
  ({request}) => request.mode === 'navigate',
  new workbox.strategies.NetworkFirst({
    cacheName: 'pages-cache-v1'
  })
);

workbox.routing.registerRoute(
  ({request}) => request.destination === 'image' || request.destination === 'font',
  new workbox.strategies.CacheFirst({
    cacheName: 'static-assets-v1',
    plugins: [
      new workbox.expiration.ExpirationPlugin({ maxEntries: 50, maxAgeSeconds: 30 * 24 * 60 * 60 })
    ]
  })
);

const bgSyncPlugin = new workbox.backgroundSync.BackgroundSyncPlugin('api-sync-queue', {
  maxRetentionTime: 24 * 60
});
workbox.routing.registerRoute(
  /\/api\/.*/
  new workbox.strategies.NetworkOnly({ plugins: [bgSyncPlugin] }),
  'POST'
);
workbox.routing.registerRoute(
  /\/api\/.*/
  new workbox.strategies.NetworkOnly({ plugins: [bgSyncPlugin] }),
  'PUT'
);

self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Crowd Management System';
  const options = {
    body: data.body || '',
    icon: 'https://via.placeholder.com/192.png',
    data: { url: data.url || '/' }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data && event.notification.data.url ? event.notification.data.url : '/'));
});

workbox.routing.setCatchHandler(async ({ event }) => {
  if (event.request.destination === 'document') {
    return caches.match('/offline.html');
  }
  return Response.error();
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
