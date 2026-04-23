const CACHE_NAME = 'nexus-ai-v2.1';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/icon-192x192.png',
  '/static/icon-512x512.png'
];

// Instalar - cachear recursos
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Ativar - limpar caches antigos
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch - estratégia stale-while-revalidate
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Não cachear chamadas API
  if (request.url.includes('/api/') || request.url.includes('/webhooks/')) {
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const fetchPromise = fetch(request).then((networkResponse) => {
        if (networkResponse.ok) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return networkResponse;
      }).catch(() => cached);

      return cached || fetchPromise;
    })
  );
});

// Notificações push (para alertas)
self.addEventListener('push', (event) => {
  const data = event.data?.json() || {};
  event.waitUntil(
    self.registration.showNotification(data.title || 'NEXUS AI', {
      body: data.body || 'Novo alerta financeiro!',
      icon: '/static/icon-192x192.png',
      badge: '/static/icon-72x72.png',
      tag: data.tag || 'nexus-alert',
      requireInteraction: true,
      actions: [
        { action: 'open', title: 'Abrir App' },
        { action: 'dismiss', title: 'Dispensar' }
      ]
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'open' || !event.action) {
    event.waitUntil(clients.openWindow('/'));
  }
});