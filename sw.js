const CACHE = 'uni-dash-v7-grades';
const CORE = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png', './assets/thmanyah/thmanyah-fonts.css', './grades.js', './grades.css'];
const NETWORK_FIRST = ['./', './index.html', './data.js'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;
  const isNetFirst = url.pathname.endsWith('/') || /\/(index\.html|data\.js|grades\.js|grades\.css)$/.test(url.pathname);
  const res = () => {
    if (isNetFirst) {
      return fetch(e.request).then(r => {
        const cp = r.clone();
        if (r.ok && !url.search) caches.open(CACHE).then(c => c.put(e.request, cp));
        return r;
      }).catch(() => caches.match(e.request).then(hit => hit || fetch(e.request)));
    }
    return caches.match(e.request).then(hit => hit || fetch(e.request).then(r => {
      const cp = r.clone();
      if (r.ok) caches.open(CACHE).then(c => c.put(e.request, cp));
      return r;
    }));
  };
  e.respondWith(res());
});
