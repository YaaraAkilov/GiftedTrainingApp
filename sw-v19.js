const CACHE='gifted-app-v19';
const ASSETS=['./','./index.html','./src/styles.css','./src/app.js','./data/questions.json?v=19','./manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('gifted-app-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  const req=e.request;
  if(req.method!=='GET') return;
  const url=new URL(req.url);
  const isAppAsset=url.pathname.endsWith('/index.html')||url.pathname.endsWith('/src/app.js')||url.pathname.endsWith('/src/styles.css')||url.pathname.endsWith('/data/questions.json')||url.pathname.endsWith('/manifest.webmanifest');
  if(isAppAsset){
    e.respondWith(fetch(req,{cache:'no-store'}).then(res=>{const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy));return res}).catch(()=>caches.match(req).then(r=>r||caches.match('./index.html'))));
    return;
  }
  e.respondWith(caches.match(req).then(r=>r||fetch(req).then(res=>{const copy=res.clone();caches.open(CACHE).then(c=>c.put(req,copy));return res}).catch(()=>caches.match('./index.html'))));
});
