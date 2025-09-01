// ======================
// memo-pwa/sw.js
// ======================

/**
 * Service Worker for the Memo PWA
 *
 * Cache Strategy:
 *  - Cache‑First: static assets (HTML, CSS, JS, etc.)
 *  - Network‑First: API data requests
 *  - Stale‑While‑Revalidate: images & fonts
 *
 * Offline support: serves cached resources and a fallback page for navigation requests.
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const DATA_CACHE = `data-${CACHE_VERSION}`;
const ASSETS_CACHE = `assets-${CACHE_VERSION}`;

// List of static resources to pre‑cache during installation
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/app.js',
  '/styles.css',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  // Add any other static files here
];

// List of image/font patterns to match for stale‑while‑revalidate
const ASSETS_PATTERNS = [
  /\.(?:png|jpg|jpeg|gif|svg|webp)$/i,
  /\.(?:woff2?|ttf|otf|eot)$/i,
];

// Fallback page for offline navigation
const OFFLINE_PAGE = '/offline.html';

self.addEventListener('install', (event) => {
  // Force the waiting service worker to become the active service worker
  self.skipWaiting();

  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
});

self.addEventListener('activate', (event) => {
  // Clean up old caches
  const cacheWhitelist = [STATIC_CACHE, DATA_CACHE, ASSETS_CACHE];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (!cacheWhitelist.includes(cacheName)) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Handle navigation requests (HTML pages)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // If the request succeeds, clone and store it in the static cache
          const clonedResponse = response.clone();
          caches.open(STATIC_CACHE).then((cache) => {
            cache.put(request, clonedResponse);
          });
          return response;
        })
        .catch(() => {
          // If network fails, try to serve from cache
          return caches.match(request).then((cached) => {
            return cached || caches.match(OFFLINE_PAGE);
          });
        })
    );
    return;
  }

  // API data requests (e.g., /api/memos)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Store a fresh copy in the data cache
          const clonedResponse = response.clone();
          caches.open(DATA_CACHE).then((cache) => {
            cache.put(request, clonedResponse);
          });
          return response;
        })
        .catch(() => {
          // If network fails, try to serve from cache
          return caches.match(request);
        })
    );
    return;
  }

  // Images & fonts: stale‑while‑revalidate
  if (ASSETS_PATTERNS.some((pattern) => pattern.test(url.pathname))) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        const fetchPromise = fetch(request)
          .then((networkResponse) => {
            // Update the cache with the fresh response
            caches.open(ASSETS_CACHE).then((cache) => {
              cache.put(request, networkResponse.clone());
            });
            return networkResponse;
          })
          .catch(() => {
            // If network fails, keep using the cached version
            return cachedResponse;
          });

        // Return cached response immediately if available, otherwise wait for network
        return cachedResponse || fetchPromise;
      })
    );
    return;
  }

  // Default: try network first, fallback to cache
  event.respondWith(
    fetch(request)
      .then((response) => {
        // Optionally cache the response for other types
        return response;
      })
      .catch(() => caches.match(request))
  );
});

// ======================
// memo-pwa/manifest.json
// ======================

/*
{
  "name": "メモ帳 PWA",
  "short_name": "メモ帳",
  "description": "シンプルなメモアプリ",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1976d2",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/icons/icon-48.png",
      "sizes": "48x48",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-72.png",
      "sizes": "72x72",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-96.png",
      "sizes": "96x96",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-144.png",
      "sizes": "144x144",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-256.png",
      "sizes": "256x256",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
*/