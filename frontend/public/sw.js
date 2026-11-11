/* ChargeCircle service worker.
 *
 * Rules:
 *  - Only GET requests are ever handled. Payments, bookings, auth and account pages are NEVER cached,
 *    so an old screen can never look like a confirmed transaction.
 *  - Requests that carry an Authorization header are never cached (they may hold personal data).
 *  - Public pages and public discovery data use network-first; the cached copy is used only when offline,
 *    and cached API answers are marked with X-ChargeCircle-Cache: stale so the UI can say so.
 */
const VERSION = "v2";
const SHELL_CACHE = `chargecircle-shell-${VERSION}`;
const PAGE_CACHE = `chargecircle-pages-${VERSION}`;
const DATA_CACHE = `chargecircle-public-data-${VERSION}`;
const OFFLINE_URL = "/offline.html";
const PRECACHE = [OFFLINE_URL, "/manifest.json", "/favicon.ico", "/icon-192.png", "/icon-512.png"];

const PRIVATE_PATHS = ["/checkout", "/bookings", "/driver", "/host", "/admin", "/auth", "/payments"];
const PUBLIC_PAGES = ["/", "/public-chargers", "/marketplace", "/map", "/compare", "/safety", "/privacy", "/terms", "/support"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) =>
      // add one by one so a single missing file can never abort installation
      Promise.all(PRECACHE.map((u) => cache.add(u).catch(() => null)))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  const keep = [SHELL_CACHE, PAGE_CACHE, DATA_CACHE];
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => !keep.includes(k)).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

function isPrivatePath(pathname) {
  return PRIVATE_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
}
function isPublicPage(pathname) {
  return PUBLIC_PAGES.some((p) => pathname === p || (p !== "/" && pathname.startsWith(p + "/")));
}

async function networkFirst(request, cacheName, markStale) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    const noStore = (response.headers.get("Cache-Control") || "").includes("no-store");
    if (response.ok && !noStore) cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) {
      if (!markStale) return cached;
      const headers = new Headers(cached.headers);
      headers.set("X-ChargeCircle-Cache", "stale");
      return new Response(await cached.blob(), { status: cached.status, statusText: cached.statusText, headers });
    }
    throw err;
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  const sameOrigin = url.origin === self.location.origin;

  // Never touch private/transactional pages or anything authenticated: always straight to the network.
  if (request.headers.has("Authorization")) return;

  if (request.mode === "navigate") {
    if (!sameOrigin) return;
    if (isPrivatePath(url.pathname)) {
      event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
      return;
    }
    if (isPublicPage(url.pathname)) {
      event.respondWith(networkFirst(request, PAGE_CACHE, false).catch(() => caches.match(OFFLINE_URL)));
      return;
    }
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  // Public, read-only discovery data (no account, no vehicle-specific query)
  if (url.pathname.includes("/api/v1/discovery/") && !url.search.includes("vehicle_id")) {
    event.respondWith(networkFirst(request, DATA_CACHE, true));
    return;
  }

  // Immutable build assets and icons
  if (sameOrigin && (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icon-"))) {
    event.respondWith(
      caches.open(SHELL_CACHE).then(async (cache) => {
        const hit = await cache.match(request);
        if (hit) return hit;
        const res = await fetch(request);
        if (res.ok) cache.put(request, res.clone());
        return res;
      })
    );
  }
});
