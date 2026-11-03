const CACHE='argentex-shell-v1.1';
const SHELL=['/','/assets/app.js','/assets/style.css','/favicon.svg','/manifest.webmanifest','/assets/icon-192.png','/assets/icon-512.png'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  const u=new URL(e.request.url);
  if(e.request.method!=='GET'||u.origin!==self.location.origin||u.pathname.startsWith('/api/'))return;
  e.respondWith(fetch(e.request).then(r=>{if(r.ok&&SHELL.includes(u.pathname)){let copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy));}return r;}).catch(()=>caches.match(e.request)));
});
