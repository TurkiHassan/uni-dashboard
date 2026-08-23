const CACHE = 'uni-dash-v3';
const CORE = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png', './assets/thmanyah/thmanyah-fonts.css'];
const NETWORK_FIRST = ['./', './index.html', './data.js'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = e.request.url;
  const isNetFirst = NETWORK_FIRST.some(p => url.endsWith(p) || url.endsWith(p.replace('./', '/uni-dashboard/')));
  const res = () => {
    if (isNetFirst) {
      return fetch(e.request).then(r => {
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, cp));
        return r;
      }).catch(() => caches.match(e.request).then(hit => hit || fetch(e.request)));
    }
    return caches.match(e.request).then(hit => hit || fetch(e.request).then(r => {
      const cp = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, cp));
      return r;
    }));
  };
  e.respondWith(res());
});
