const CACHE_PREFIX = "ichigodb-native-shell";
const CACHE_VERSION = "v2";
const CACHE_NAME = `${CACHE_PREFIX}-${CACHE_VERSION}`;

const SHELL_ASSETS = [
  "manifest.webmanifest",
  "icons/icon-180.png",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-512-maskable.png",
  "app-sw.js",
];
const STATIC_MARKERS = ["/app/static/", "/static/"];
const SHELL_ASSET_PATHS = new Set(SHELL_ASSETS);
const SHELL_CACHE_KEY_ROOT = new URL("/__ichigodb_shell_cache__/", self.location.origin).toString();
const STATIC_BASE_URLS = buildStaticBaseUrls();

let lastKnownOnline = null;

const toCacheKey = (assetPath) => new URL(assetPath, SHELL_CACHE_KEY_ROOT).toString();

function buildStaticBaseUrls() {
  const scopePathname = new URL(self.registration.scope).pathname;
  const basePaths = new Set();

  if (scopePathname.endsWith("/")) {
    basePaths.add(scopePathname);
  }

  const matchedMarker = STATIC_MARKERS.find((marker) => scopePathname.includes(marker));
  if (matchedMarker) {
    const markerIndex = scopePathname.indexOf(matchedMarker);
    const pathPrefix = scopePathname.slice(0, markerIndex);
    for (const candidateMarker of STATIC_MARKERS) {
      basePaths.add(`${pathPrefix}${candidateMarker}`);
    }
  }

  for (const marker of STATIC_MARKERS) {
    basePaths.add(marker);
  }

  return Array.from(basePaths).map((basePath) => new URL(basePath, self.location.origin).toString());
}

const listAssetCandidates = (assetPath) =>
  Array.from(new Set(STATIC_BASE_URLS.map((baseUrl) => new URL(assetPath, baseUrl).toString())));

const resolveAssetPath = (pathname) => {
  for (const marker of STATIC_MARKERS) {
    const markerIndex = pathname.indexOf(marker);
    if (markerIndex >= 0) {
      const assetPath = pathname.slice(markerIndex + marker.length);
      if (assetPath) {
        return assetPath;
      }
    }
  }
  return "";
};

const extractShellAssetPath = (requestUrl) => {
  const url = new URL(requestUrl, self.location.origin);
  if (url.origin !== self.location.origin) {
    return "";
  }
  const assetPath = resolveAssetPath(url.pathname);
  return SHELL_ASSET_PATHS.has(assetPath) ? assetPath : "";
};

const cacheAssetResponse = async (cache, assetPath, response) => {
  if (!response || !response.ok) {
    return;
  }
  try {
    await cache.put(toCacheKey(assetPath), response.clone());
  } catch (error) {
    console.warn("[app-sw] Failed to cache shell asset:", assetPath, error);
  }
};

const fetchFirstAvailableAsset = async (candidateUrls) => {
  let hadNetworkError = false;

  for (const candidateUrl of candidateUrls) {
    try {
      const response = await fetch(candidateUrl, { cache: "no-store", credentials: "same-origin" });
      if (response && response.ok) {
        return { response, hadNetworkError };
      }
    } catch (error) {
      hadNetworkError = true;
    }
  }

  return { response: null, hadNetworkError };
};

const broadcastNetworkState = async (online, source) => {
  if (lastKnownOnline === online) {
    return;
  }
  lastKnownOnline = online;

  const windowClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const client of windowClients) {
    client.postMessage({
      type: "ichigodb:network-status",
      online,
      source,
      at: Date.now(),
    });
  }
};

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      await Promise.allSettled(
        SHELL_ASSETS.map(async (assetPath) => {
          const { response } = await fetchFirstAvailableAsset(listAssetCandidates(assetPath));
          if (response) {
            await cacheAssetResponse(cache, assetPath, response);
            return;
          }
          console.warn("[app-sw] Failed to precache shell asset:", assetPath);
        })
      );
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key.startsWith(`${CACHE_PREFIX}-`) && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      );
      await self.clients.claim();
    })()
  );
});

self.addEventListener("message", (event) => {
  if (!event.data || event.data.type !== "ichigodb:network-status-request") {
    return;
  }

  if (!event.source || typeof event.source.postMessage !== "function") {
    return;
  }

  event.source.postMessage({
    type: "ichigodb:network-status",
    online: lastKnownOnline !== false,
    source: "status-request",
    at: Date.now(),
  });
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const assetPath = extractShellAssetPath(event.request.url);
  if (!assetPath) {
    return;
  }

  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      const cacheKey = toCacheKey(assetPath);
      const fetchCandidates = Array.from(new Set([event.request.url, ...listAssetCandidates(assetPath)]));
      const cached = await cache.match(cacheKey, { ignoreSearch: true });

      if (cached) {
        event.waitUntil(
          (async () => {
            const { response, hadNetworkError } = await fetchFirstAvailableAsset(fetchCandidates);
            if (response) {
              await cacheAssetResponse(cache, assetPath, response);
              await broadcastNetworkState(true, "shell-refresh");
            } else if (hadNetworkError) {
              await broadcastNetworkState(false, "shell-refresh");
            }
          })()
        );
        return cached;
      }

      const { response, hadNetworkError } = await fetchFirstAvailableAsset(fetchCandidates);
      if (response) {
        await cacheAssetResponse(cache, assetPath, response);
        await broadcastNetworkState(true, "shell-network");
        return response;
      }

      if (hadNetworkError) {
        await broadcastNetworkState(false, "shell-network");
      }

      const fallback = await cache.match(cacheKey, { ignoreSearch: true });
      if (fallback) {
        return fallback;
      }

      return Response.error();
    })()
  );
});
