importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js');

workbox.setConfig({ debug: false });
workbox.core.clientsClaim();

workbox.precaching.precacheAndRoute([{"revision":"605b3e10eb9a84e234755b6afc5a6f1b","url":"css/app.css"},{"revision":"84495fa63d59647760bb2aeb3f31753e","url":"css/contact.css"},{"revision":"d5a8fe5612330fee581d3f83b37ef858","url":"css/flatpickr.min.css"},{"revision":"629164d0ed44baadbdb22be031590ae1","url":"css/login.css"},{"revision":"b737e2195f858a14a087c30c31e60d13","url":"css/sci_fi_theme.css"},{"revision":"1a46f7353965f2379d59c00af4f47911","url":"css/site.css"},{"revision":"ac7f0643a6ded0a5fdecb17b9754ba84","url":"feedback/889c2f486f7f4bb8b69f6d076787c85d.png"},{"revision":"ac7f0643a6ded0a5fdecb17b9754ba84","url":"feedback/8d713614d32f45d4b91566ea5b7c7c7f.png"},{"revision":"ac7f0643a6ded0a5fdecb17b9754ba84","url":"feedback/b0e5a3d3845e4337abf2e616d2b6f1eb.png"},{"revision":"c6a26615a948528950c5de854bc95c9a","url":"js/admin_users.js"},{"revision":"cc8eb3536ad5050a376dbb17b3a4e2dc","url":"js/alert_stats.js"},{"revision":"80094fc7b426c471feafc108097475d1","url":"js/camera_create.js"},{"revision":"184cff25e586ad71c1e88194bcf41f70","url":"js/camera_table.js"},{"revision":"187ffe7a12d1079ea1653198f9e19187","url":"js/chart.umd.min.js"},{"revision":"f3adb031ff6977be4c66edb0ffb61d76","url":"js/chartjs-plugin-datalabels.min.js"},{"revision":"f9c1245b398e051c4c51c08621252e7b","url":"js/chartjs-plugin-zoom.min.js"},{"revision":"c359e1112ca3aa68a194eec46f73ed0a","url":"js/dashboard_graph.js"},{"revision":"5302d7f2278fc49cb3ca228eb4555bd5","url":"js/dashboard_map.js"},{"revision":"9deb4fe731dec69eafec81261ad63fb2","url":"js/email_alerts.js"},{"revision":"573a6afa3eb4a2135c79af62f2e017ea","url":"js/face_db_page.js"},{"revision":"ec5c1320ea39dfb52c95eeab78840d69","url":"js/face_db_search_live.js"},{"revision":"672cb04175ae9b180528d5302da4b698","url":"js/face_db_source.js"},{"revision":"ff98a4dc930264379b89b89ecbb7516a","url":"js/feedback.js"},{"revision":"5c4cd510c21779627a4973c4f6e435e5","url":"js/flatpickr.min.js"},{"revision":"dfb8888916e2761f06999f32cfb3697b","url":"js/i18n.js"},{"revision":"867b8ba6bdda35b4dfdb57c36ed9a737","url":"js/identity_profile.js"},{"revision":"dccd8d6ce188aff01cc91edc1ccfc93a","url":"js/login.js"},{"revision":"b43c1e45224fb1a6954ebbd7054c4100","url":"js/mjpeg_feed.js"},{"revision":"92056c332993c201fbf670b7c835c980","url":"js/page_transition.js"},{"revision":"664abddccf6b43f3b036df526a77a4a0","url":"js/photo_uploader.js"},{"revision":"eab51a6ab534a49607a06965f166074d","url":"js/ppe_report.js"},{"revision":"d85a3851c0179bec3443454960c3f5e9","url":"js/profile_avatar.js"},{"revision":"6d72852f145994ba21524dd4523503a1","url":"js/profile.js"},{"revision":"fa0c52a551a65ad318335e512c85a41d","url":"js/pwa.js"},{"revision":"a6b6b1f6d4806e3dc809538e4f3b836d","url":"js/report.js"},{"revision":"bff5dbcc4eed1cb992efa605525cbcb3","url":"js/settings.js"},{"revision":"12bc0f14871c57bc8df902d6319bf845","url":"js/stats_utils.js"},{"revision":"b81e469a3e9050aed3b14705416c013b","url":"js/suggestions.js"},{"revision":"184a56243f1e7eb8e845dca473219b20","url":"js/theme.js"},{"revision":"dcf1ecb9aa05696d7f58dc33c2f3d40c","url":"js/validation.js"},{"revision":"48630c1c10f6bd9be11060c2754fb39e","url":"logo1.png"},{"revision":"d5fedae53391222f0989631c47967655","url":"logo2.png"},{"revision":"725cfd82bd04892eb5c2572970c4cf92","url":"manifest.webmanifest"},{"revision":"65488bef2495a3173ab82bc406d3aa24","url":"offline.html"},{"revision":"e44878370776106937a0804ef497566e","url":"sw-dev.js"}]);

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
