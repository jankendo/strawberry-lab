"""Safe offline runtime bridge for resilient status feedback."""

from __future__ import annotations

import streamlit.components.v1 as components

_OFFLINE_RUNTIME_BRIDGE = """
<script>
(function () {
  let parentWindow = null;
  let doc = null;
  try {
    parentWindow = window.parent;
    doc = parentWindow && parentWindow.document ? parentWindow.document : null;
  } catch (error) {
    return;
  }
  if (!parentWindow || !doc || !doc.body) {
    return;
  }

  const stateKey = "__ichigodbOfflineRuntimeState";
  const state = parentWindow[stateKey] || {};
  parentWindow[stateKey] = state;
  if (state.initialized && typeof state.refresh === "function") {
    state.refresh("streamlit-rerun");
    return;
  }

  const STYLE_ID = "sl-offline-runtime-style";
  const BANNER_ID = "sl-offline-runtime-banner";
  const RECONNECT_TEXT_RE =
    /(reconnect|connecting|connection\\s?(lost|error|interrupted)|retry|server\\s+disconnected|streamlit\\s+disconnected|再接続|接続中|通信エラー|切断|再試行)/i;
  const RECONNECT_SELECTOR = [
    '[data-testid="stConnectionStatus"]',
    '[data-testid*="Status"]',
    '[role="alert"]',
    '[aria-live="assertive"]',
    '[aria-live="polite"]',
  ].join(",");

  function ensureStyle() {
    if (doc.getElementById(STYLE_ID) || !doc.head) {
      return;
    }
    const style = doc.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
#${BANNER_ID} {
  position: fixed;
  top: calc(env(safe-area-inset-top, 0px) + 0.58rem);
  left: 50%;
  transform: translate(-50%, -8px);
  max-width: min(34rem, calc(100vw - 1rem));
  min-height: 1.9rem;
  padding: 0.34rem 0.78rem;
  border-radius: 999px;
  border: 1px solid #d7dde7;
  background: rgba(255, 255, 255, 0.96);
  color: #1f2937;
  font-size: 0.78rem;
  font-weight: 650;
  line-height: 1.2;
  box-shadow: 0 6px 18px rgba(17, 24, 39, 0.12);
  backdrop-filter: blur(6px);
  pointer-events: none;
  opacity: 0;
  transition: opacity 180ms ease, transform 180ms ease;
  z-index: 48;
}
#${BANNER_ID}[data-visible="1"] {
  opacity: 1;
  transform: translate(-50%, 0);
}
#${BANNER_ID}[data-status="offline"] {
  border-color: #fca5a5;
  background: rgba(254, 242, 242, 0.96);
  color: #991b1b;
}
#${BANNER_ID}[data-status="reconnecting"] {
  border-color: #fde68a;
  background: rgba(255, 251, 235, 0.96);
  color: #92400e;
}
#${BANNER_ID}[data-status="online"] {
  border-color: #86efac;
  background: rgba(236, 253, 243, 0.96);
  color: #166534;
}
@media (max-width: 820px) {
  #${BANNER_ID} {
    max-width: calc(100vw - 0.8rem);
    font-size: 0.76rem;
    padding: 0.34rem 0.65rem;
    top: calc(env(safe-area-inset-top, 0px) + 0.5rem);
  }
}
    `;
    doc.head.appendChild(style);
  }

  function ensureBanner() {
    let banner = doc.getElementById(BANNER_ID);
    if (!banner) {
      banner = doc.createElement("div");
      banner.id = BANNER_ID;
      banner.setAttribute("role", "status");
      banner.setAttribute("aria-live", "polite");
      banner.setAttribute("aria-atomic", "true");
      banner.setAttribute("data-visible", "0");
      banner.setAttribute("data-status", "online");
      doc.body.appendChild(banner);
    }
    return banner;
  }

  function isVisible(element) {
    if (!element || element.hidden) {
      return false;
    }
    const computed = parentWindow.getComputedStyle ? parentWindow.getComputedStyle(element) : null;
    if (!computed) {
      return true;
    }
    if (computed.display === "none" || computed.visibility === "hidden") {
      return false;
    }
    if (Number(computed.opacity || "1") === 0) {
      return false;
    }
    const rect = element.getBoundingClientRect ? element.getBoundingClientRect() : null;
    if (!rect) {
      return true;
    }
    return rect.width > 0 || rect.height > 0;
  }

  function detectReconnectingOverlay() {
    if (!doc.querySelectorAll) {
      return false;
    }
    const candidates = doc.querySelectorAll(RECONNECT_SELECTOR);
    const limit = Math.min(candidates.length, 24);
    for (let index = 0; index < limit; index += 1) {
      const element = candidates[index];
      if (!isVisible(element)) {
        continue;
      }
      const testId = (element.getAttribute && element.getAttribute("data-testid")) || "";
      const text = (element.textContent || "").trim();
      if (!text && !/stConnectionStatus/i.test(testId)) {
        continue;
      }
      if (RECONNECT_TEXT_RE.test(`${testId} ${text}`)) {
        return true;
      }
    }
    return false;
  }

  function clearHideTimer() {
    if (!state.hideTimer) {
      return;
    }
    parentWindow.clearTimeout(state.hideTimer);
    state.hideTimer = null;
  }

  function postServiceWorkerMessage(message) {
    const navigatorRef = parentWindow.navigator;
    if (!navigatorRef || !navigatorRef.serviceWorker) {
      return;
    }
    const serviceWorker = navigatorRef.serviceWorker;
    if (serviceWorker.controller && typeof serviceWorker.controller.postMessage === "function") {
      serviceWorker.controller.postMessage(message);
      return;
    }
    if (!serviceWorker.ready || typeof serviceWorker.ready.then !== "function") {
      return;
    }
    serviceWorker.ready
      .then(function (registration) {
        const activeWorker = registration && registration.active;
        if (activeWorker && typeof activeWorker.postMessage === "function") {
          activeWorker.postMessage(message);
        }
      })
      .catch(function () {
        // ignore service worker readiness failures
      });
  }

  function requestServiceWorkerStatus(source) {
    postServiceWorkerMessage({
      type: "ichigodb:network-status-request",
      source: source || "runtime-request",
      at: Date.now(),
    });
  }

  function reportServiceWorkerStatus(online, source) {
    postServiceWorkerMessage({
      type: "ichigodb:network-status-report",
      online: !!online,
      source: source || "runtime-window-event",
      at: Date.now(),
    });
  }

  function resolveStatus() {
    const effectiveOnline =
      typeof state.serviceWorkerOnline === "boolean" ? state.serviceWorkerOnline : state.browserOnline;
    if (effectiveOnline === false) {
      return "offline";
    }
    if (state.reconnecting) {
      return "reconnecting";
    }
    return "online";
  }

  function statusLabel(status) {
    if (status === "offline") {
      return "オフライン: 通信回復を待っています";
    }
    if (status === "reconnecting") {
      return "再接続中…";
    }
    return "オンラインに復帰しました";
  }

  function hideBanner() {
    ensureBanner().setAttribute("data-visible", "0");
  }

  function showBanner(status, autoHideMs) {
    const banner = ensureBanner();
    banner.setAttribute("data-status", status);
    banner.textContent = statusLabel(status);
    banner.setAttribute("data-visible", "1");
    clearHideTimer();
    if (!autoHideMs) {
      return;
    }
    state.hideTimer = parentWindow.setTimeout(function () {
      hideBanner();
    }, autoHideMs);
  }

  function renderStatus() {
    const status = resolveStatus();
    const changed = status !== state.lastStatus;
    if (status === "online") {
      if (changed && state.hasWarned) {
        showBanner(status, 2200);
      } else {
        hideBanner();
      }
    } else {
      state.hasWarned = true;
      showBanner(status, 0);
    }
    state.lastStatus = status;
  }

  function setReconnecting(value) {
    const normalized = !!value;
    if (state.reconnecting === normalized) {
      return;
    }
    state.reconnecting = normalized;
    renderStatus();
  }

  function queueReconnectCheck() {
    if (state.reconnectCheckQueued) {
      return;
    }
    state.reconnectCheckQueued = true;
    const flush = function () {
      state.reconnectCheckQueued = false;
      setReconnecting(detectReconnectingOverlay());
    };
    if (typeof parentWindow.requestAnimationFrame === "function") {
      parentWindow.requestAnimationFrame(flush);
      return;
    }
    parentWindow.setTimeout(flush, 32);
  }

  function setBrowserOnline(online, source) {
    state.browserOnline = !!online;
    if (!state.browserOnline) {
      state.serviceWorkerOnline = false;
    } else {
      state.serviceWorkerOnline = null;
    }
    renderStatus();
    reportServiceWorkerStatus(state.browserOnline, source || "window-event");
    if (state.browserOnline) {
      requestServiceWorkerStatus(source || "window-online");
    }
  }

  ensureStyle();
  ensureBanner();

  state.initialized = true;
  state.browserOnline = !(parentWindow.navigator && parentWindow.navigator.onLine === false);
  state.serviceWorkerOnline = null;
  state.reconnecting = false;
  state.lastStatus = "";
  state.hasWarned = false;
  state.hideTimer = null;
  state.reconnectCheckQueued = false;

  const navigatorRef = parentWindow.navigator;
  if (parentWindow.addEventListener) {
    parentWindow.addEventListener("online", function () {
      setBrowserOnline(true, "window-online");
    });
    parentWindow.addEventListener("offline", function () {
      setBrowserOnline(false, "window-offline");
    });
  }

  if (navigatorRef && navigatorRef.serviceWorker && typeof navigatorRef.serviceWorker.addEventListener === "function") {
    navigatorRef.serviceWorker.addEventListener("message", function (event) {
      const data = event && event.data ? event.data : null;
      if (!data || data.type !== "ichigodb:network-status" || typeof data.online !== "boolean") {
        return;
      }
      state.serviceWorkerOnline = data.online;
      renderStatus();
      queueReconnectCheck();
    });
    navigatorRef.serviceWorker.addEventListener("controllerchange", function () {
      requestServiceWorkerStatus("controllerchange");
    });
  }

  if (typeof parentWindow.MutationObserver === "function") {
    const observer = new parentWindow.MutationObserver(function () {
      queueReconnectCheck();
    });
    observer.observe(doc.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "style", "hidden", "aria-hidden", "data-testid"],
    });
  }

  state.refresh = function (source) {
    ensureStyle();
    ensureBanner();
    renderStatus();
    queueReconnectCheck();
    requestServiceWorkerStatus(source || "runtime-refresh");
  };

  renderStatus();
  queueReconnectCheck();
  reportServiceWorkerStatus(state.browserOnline, "runtime-init");
  requestServiceWorkerStatus("runtime-init");
})();
</script>
"""


def inject_offline_runtime() -> None:
    """Inject a lightweight, non-destructive offline/reconnecting status bridge."""
    components.html(_OFFLINE_RUNTIME_BRIDGE, height=0)
