"""View Transition helpers for progressive mobile list/detail flows."""

from __future__ import annotations

from html import escape
import json
import re

import streamlit as st
import streamlit.components.v1 as components

_TOKEN_SANITIZER_RE = re.compile(r"[^A-Za-z0-9_-]+")
_MAX_TOKEN_LENGTH = 64


def _normalize_token(value: object, *, fallback: str) -> str:
    text = _TOKEN_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_")
    if not text:
        return fallback
    return text[:_MAX_TOKEN_LENGTH]


def _normalize_optional_token(value: object | None) -> str | None:
    text = _TOKEN_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_")
    if not text:
        return None
    return text[:_MAX_TOKEN_LENGTH]


def _build_transition_style(scope: str, *, duration_ms: int) -> str:
    animation_name = f"sl-vt-enter-{scope}"
    return f"""
<style>
.sl-vt-trigger-marker,
.sl-vt-shared-marker,
[data-sl-vt-root] {{
    display: none !important;
}}

[data-sl-vt-shared-overlay] {{
    pointer-events: none;
    position: fixed;
    z-index: 2147483600;
    margin: 0;
    transform-origin: top left;
    will-change: transform, opacity, border-radius;
    overflow: hidden;
    contain: layout style paint;
}}

[data-sl-vt-shared-overlay] img {{
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
}}

[data-sl-vt-shared-overlay-text] {{
    display: flex;
    align-items: center;
    justify-content: flex-start;
    width: 100%;
    height: 100%;
    padding: 0.4rem 0.6rem;
    box-sizing: border-box;
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--text-color, #111827);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

@media (max-width: 960px) {{
    :root[data-sl-vt-active-scope="{scope}"] [data-testid="stMainBlockContainer"] {{
        will-change: opacity, transform;
    }}
    :root[data-sl-vt-active-scope="{scope}"].sl-vt-native-enter [data-testid="stMainBlockContainer"] {{
        opacity: 0.985;
        transform: translateY(6px);
    }}
    :root[data-sl-vt-active-scope="{scope}"].sl-vt-fallback-enter [data-testid="stMainBlockContainer"] {{
        animation: {animation_name} {duration_ms}ms cubic-bezier(0.2, 0, 0.2, 1) both;
    }}
    :root[data-sl-vt-active-scope="{scope}"]::view-transition-old(root),
    :root[data-sl-vt-active-scope="{scope}"]::view-transition-new(root) {{
        animation-duration: {duration_ms}ms;
        animation-timing-function: cubic-bezier(0.2, 0, 0.2, 1);
    }}
}}

@media (prefers-reduced-motion: reduce) {{
    :root[data-sl-vt-active-scope="{scope}"]::view-transition-old(root),
    :root[data-sl-vt-active-scope="{scope}"]::view-transition-new(root) {{
        animation-duration: 1ms !important;
    }}
    :root[data-sl-vt-active-scope="{scope}"].sl-vt-fallback-enter [data-testid="stMainBlockContainer"] {{
        animation: none !important;
    }}
}}

@keyframes {animation_name} {{
    from {{
        opacity: 0;
        transform: translateY(10px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}
</style>
"""


def _build_transition_script(config_json: str) -> str:
    return """
<script>
(function () {
  const config = __CONFIG__;
  let parentWindow = null;
  let doc = null;
  try {
    parentWindow = window.parent;
    doc = parentWindow && parentWindow.document ? parentWindow.document : null;
  } catch (error) {
    return;
  }
  if (!parentWindow || !doc || !doc.documentElement) {
    return;
  }

  const scope = String(config.scope || "").trim();
  if (!scope) {
    return;
  }

  const root = doc.documentElement;
  if (!doc.body) {
    return;
  }
  const storeKey = "__slViewTransitionStore";
  const pendingKey = "__slViewTransitionPending";
  const store = parentWindow[storeKey] || {};
  parentWindow[storeKey] = store;
  const scopeStore = store[scope] || {};
  store[scope] = scopeStore;
  const durationMs = Math.max(120, Math.min(Number(config.durationMs || 180), 260));

  function setPhase(phase) {
    root.setAttribute("data-sl-vt-phase", phase);
    const running = phase === "running" || phase === "fallback-enter";
    root.classList.toggle("sl-vt-running", running);
  }

  function readPending() {
    try {
      const raw = parentWindow.sessionStorage.getItem(pendingKey);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function writePending(value) {
    try {
      if (!value) {
        parentWindow.sessionStorage.removeItem(pendingKey);
      } else {
        parentWindow.sessionStorage.setItem(pendingKey, JSON.stringify(value));
      }
    } catch (error) {
      // ignore storage failures
    }
  }

  function rectToObject(rect) {
    return {
      left: Number(rect.left || 0),
      top: Number(rect.top || 0),
      width: Number(rect.width || 0),
      height: Number(rect.height || 0),
    };
  }

  function parseRadius(value, fallback) {
    const parsed = Number.parseFloat(String(value || ""));
    if (Number.isFinite(parsed) && parsed >= 0) {
      return parsed;
    }
    return Number(fallback || 0);
  }

  function findFollowingElement(marker, candidates) {
    for (let index = 0; index < candidates.length; index += 1) {
      const candidate = candidates[index];
      if (marker.compareDocumentPosition(candidate) & Node.DOCUMENT_POSITION_FOLLOWING) {
        return candidate;
      }
    }
    return null;
  }

  function resolveSharedCandidate(element) {
    if (!element || typeof element.getBoundingClientRect !== "function") {
      return null;
    }
    if (String(element.tagName || "").toUpperCase() === "IMG") {
      return element;
    }
    if (element.querySelector) {
      const image = element.querySelector("img");
      if (image) {
        return image;
      }
    }
    return element;
  }

  function cleanupSharedOverlays() {
    const overlays = doc.querySelectorAll('[data-sl-vt-shared-overlay="1"]');
    overlays.forEach(function (overlay) {
      if (overlay && overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
    });
  }

  function mapTriggerMarkers() {
    const markers = doc.querySelectorAll(
      '[data-sl-vt-trigger-marker][data-sl-vt-scope="' + scope + '"]'
    );
    if (!markers.length) {
      return;
    }
    const buttons = Array.prototype.slice.call(doc.querySelectorAll("button"));
    markers.forEach(function (marker) {
      const action = String(marker.getAttribute("data-sl-vt-action") || "toggle");
      const sharedKey = String(marker.getAttribute("data-sl-vt-shared-key") || "").trim();
      const sharedRole = String(marker.getAttribute("data-sl-vt-shared-role") || "source").trim();
      const targetButton = findFollowingElement(marker, buttons);
      if (!targetButton) {
        return;
      }
      targetButton.setAttribute("data-sl-vt-trigger", "1");
      targetButton.setAttribute("data-sl-vt-scope", scope);
      targetButton.setAttribute("data-sl-vt-action", action);
      if (sharedKey) {
        targetButton.setAttribute("data-sl-vt-shared-key", sharedKey);
        targetButton.setAttribute("data-sl-vt-shared-role", sharedRole === "target" ? "target" : "source");
      } else {
        targetButton.removeAttribute("data-sl-vt-shared-key");
        targetButton.removeAttribute("data-sl-vt-shared-role");
      }
    });
  }

  function mapSharedMarkers() {
    const markers = doc.querySelectorAll(
      '[data-sl-vt-shared-marker][data-sl-vt-scope="' + scope + '"]'
    );
    if (!markers.length) {
      return;
    }
    const candidates = Array.prototype.slice.call(
      doc.querySelectorAll(
        '[data-testid="stImage"], [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"], button'
      )
    );
    markers.forEach(function (marker) {
      const sharedKey = String(marker.getAttribute("data-sl-vt-shared-key") || "").trim();
      if (!sharedKey) {
        return;
      }
      const sharedRole =
        String(marker.getAttribute("data-sl-vt-shared-role") || "source").trim() === "target"
          ? "target"
          : "source";
      const targetElement = findFollowingElement(marker, candidates);
      if (!targetElement) {
        return;
      }
      targetElement.setAttribute("data-sl-vt-shared-element", "1");
      targetElement.setAttribute("data-sl-vt-shared-scope", scope);
      targetElement.setAttribute("data-sl-vt-shared-key", sharedKey);
      targetElement.setAttribute("data-sl-vt-shared-role", sharedRole);
    });
  }

  function findSharedElement(sharedKey, roleHint) {
    const key = String(sharedKey || "").trim();
    if (!key) {
      return null;
    }
    const all = Array.prototype.slice.call(
      doc.querySelectorAll(
        '[data-sl-vt-shared-element="1"][data-sl-vt-shared-scope="' +
          scope +
          '"][data-sl-vt-shared-key="' +
          key +
          '"]'
      )
    );
    if (!all.length) {
      return null;
    }
    const normalizedRole = roleHint === "target" ? "target" : roleHint === "source" ? "source" : "";
    const pool =
      normalizedRole !== ""
        ? all.filter(function (node) {
            return String(node.getAttribute("data-sl-vt-shared-role") || "") === normalizedRole;
          })
        : all;
    const candidates = pool.length ? pool : all;
    let best = null;
    let bestArea = 0;
    candidates.forEach(function (node) {
      const candidate = resolveSharedCandidate(node);
      if (!candidate) {
        return;
      }
      const rect = candidate.getBoundingClientRect();
      const area = Math.max(0, Number(rect.width || 0)) * Math.max(0, Number(rect.height || 0));
      if (area > bestArea) {
        best = candidate;
        bestArea = area;
      }
    });
    if (best) {
      return best;
    }
    return resolveSharedCandidate(candidates[0]);
  }

  function captureSharedSnapshot(sharedKey, roleHint) {
    const key = String(sharedKey || "").trim();
    if (!key) {
      return null;
    }
    const sourceElement = findSharedElement(key, roleHint === "target" ? "target" : "source");
    if (!sourceElement) {
      return null;
    }
    const rect = sourceElement.getBoundingClientRect();
    if (!rect || rect.width < 8 || rect.height < 8) {
      return null;
    }
    const computed = parentWindow.getComputedStyle ? parentWindow.getComputedStyle(sourceElement) : null;
    const image = String(sourceElement.tagName || "").toUpperCase() === "IMG" ? sourceElement : null;
    const imageSrc = image ? String(image.currentSrc || image.src || "").trim() : "";
    return {
      key: key,
      role: roleHint === "target" ? "target" : "source",
      rect: rectToObject(rect),
      radius: parseRadius(computed ? computed.borderRadius : "", 12),
      bg: computed ? String(computed.backgroundColor || "") : "",
      src: imageSrc,
      text: imageSrc ? "" : String(sourceElement.textContent || "").trim().slice(0, 120),
    };
  }

  function buildSharedOverlay(snapshot, fromRect) {
    if (!snapshot || !fromRect) {
      return null;
    }
    const overlay = doc.createElement("div");
    overlay.setAttribute("data-sl-vt-shared-overlay", "1");
    overlay.style.left = String(fromRect.left) + "px";
    overlay.style.top = String(fromRect.top) + "px";
    overlay.style.width = String(fromRect.width) + "px";
    overlay.style.height = String(fromRect.height) + "px";
    overlay.style.opacity = "0.98";
    overlay.style.borderRadius = String(Math.max(6, Number(snapshot.radius || 12))) + "px";
    overlay.style.background = snapshot.bg || "rgba(15, 23, 42, 0.08)";
    overlay.style.boxShadow = "0 10px 24px rgba(15, 23, 42, 0.18)";

    if (snapshot.src) {
      const image = doc.createElement("img");
      image.src = snapshot.src;
      image.alt = "";
      image.loading = "eager";
      overlay.appendChild(image);
    } else {
      const textNode = doc.createElement("div");
      textNode.setAttribute("data-sl-vt-shared-overlay-text", "1");
      textNode.textContent = String(snapshot.text || " ");
      overlay.appendChild(textNode);
    }
    return overlay;
  }

  function animateSharedToTarget(pending) {
    const shared = pending && pending.shared ? pending.shared : null;
    if (!shared || !shared.rect || !shared.key) {
      return false;
    }

    const fromRect = {
      left: Number(shared.rect.left || 0),
      top: Number(shared.rect.top || 0),
      width: Number(shared.rect.width || 0),
      height: Number(shared.rect.height || 0),
    };
    if (fromRect.width < 8 || fromRect.height < 8) {
      return false;
    }

    const targetRole = shared.role === "target" ? "source" : "target";
    const targetElement = findSharedElement(shared.key, targetRole);
    if (!targetElement) {
      return false;
    }
    const toRectRaw = targetElement.getBoundingClientRect();
    if (!toRectRaw || toRectRaw.width < 8 || toRectRaw.height < 8) {
      return false;
    }
    const toRect = rectToObject(toRectRaw);
    const overlay = buildSharedOverlay(shared, fromRect);
    if (!overlay) {
      return false;
    }

    const targetComputed = parentWindow.getComputedStyle ? parentWindow.getComputedStyle(targetElement) : null;
    const targetRadius = parseRadius(targetComputed ? targetComputed.borderRadius : "", Number(shared.radius || 12));
    const deltaX = toRect.left - fromRect.left;
    const deltaY = toRect.top - fromRect.top;
    const scaleX = fromRect.width > 0 ? toRect.width / fromRect.width : 1;
    const scaleY = fromRect.height > 0 ? toRect.height / fromRect.height : 1;
    const sharedDuration = Math.max(140, Math.min(durationMs + 20, 260));
    const priorOpacity = targetElement.style.opacity;
    const priorWillChange = targetElement.style.willChange;
    const priorTransition = targetElement.style.transition;

    targetElement.style.opacity = "0.02";
    targetElement.style.willChange = "opacity";
    doc.body.appendChild(overlay);

    function finalize() {
      targetElement.style.opacity = priorOpacity;
      targetElement.style.willChange = priorWillChange;
      targetElement.style.transition = priorTransition;
      if (overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
    }

    if (overlay.animate) {
      const animation = overlay.animate(
        [
          {
            transform: "translate3d(0px, 0px, 0px) scale(1, 1)",
            opacity: 0.98,
            borderRadius: String(Math.max(6, Number(shared.radius || 12))) + "px",
          },
          {
            transform:
              "translate3d(" +
              String(deltaX) +
              "px, " +
              String(deltaY) +
              "px, 0px) scale(" +
              String(scaleX) +
              ", " +
              String(scaleY) +
              ")",
            opacity: 0.92,
            borderRadius: String(Math.max(6, Number(targetRadius || 12))) + "px",
          },
        ],
        {
          duration: sharedDuration,
          easing: "cubic-bezier(0.22, 1, 0.36, 1)",
          fill: "forwards",
        }
      );
      if (targetElement.animate) {
        targetElement.animate(
          [{ opacity: 0.05 }, { opacity: 1 }],
          {
            duration: Math.max(120, sharedDuration - 16),
            easing: "ease-out",
            delay: 12,
            fill: "both",
          }
        );
      }
      animation.finished.then(finalize).catch(finalize);
      return true;
    }

    overlay.style.transition =
      "transform " +
      String(sharedDuration) +
      "ms cubic-bezier(0.22, 1, 0.36, 1), opacity " +
      String(sharedDuration) +
      "ms ease-out, border-radius " +
      String(sharedDuration) +
      "ms ease-out";
    parentWindow.requestAnimationFrame(function () {
      overlay.style.transform =
        "translate3d(" +
        String(deltaX) +
        "px, " +
        String(deltaY) +
        "px, 0px) scale(" +
        String(scaleX) +
        ", " +
        String(scaleY) +
        ")";
      overlay.style.opacity = "0.92";
      overlay.style.borderRadius = String(Math.max(6, Number(targetRadius || 12))) + "px";
      targetElement.style.transition = "opacity " + String(Math.max(120, sharedDuration - 16)) + "ms ease-out";
      targetElement.style.opacity = "1";
    });
    parentWindow.setTimeout(finalize, sharedDuration + 48);
    return true;
  }

  function getScopeMarker() {
    const markers = doc.querySelectorAll('[data-sl-vt-root][data-sl-vt-scope="' + scope + '"]');
    if (!markers.length) {
      return null;
    }
    return markers[markers.length - 1];
  }

  cleanupSharedOverlays();
  mapTriggerMarkers();
  mapSharedMarkers();
  const marker = getScopeMarker();
  if (!marker) {
    return;
  }

  const currentState = String(marker.getAttribute("data-sl-vt-state") || "");
  const enabled = marker.getAttribute("data-sl-vt-enabled") === "1";
  const mobileOnly = marker.getAttribute("data-sl-vt-mobile-only") !== "0";
  const viewportWidth = parentWindow.innerWidth || doc.documentElement.clientWidth || 0;
  const allowByViewport = !mobileOnly || viewportWidth <= 960;
  const reduceMotion = !!(
    parentWindow.matchMedia &&
    parentWindow.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
  const nativeSupported = typeof doc.startViewTransition === "function";
  const transitionsEnabled = enabled && allowByViewport && !reduceMotion;

  root.setAttribute("data-sl-vt-active-scope", scope);
  root.setAttribute("data-sl-vt-current-state", currentState);
  root.setAttribute("data-sl-vt-support", nativeSupported ? "native" : "fallback");
  root.setAttribute("data-sl-vt-enhanced", transitionsEnabled ? "1" : "0");

  scopeStore.currentState = currentState;
  scopeStore.transitionsEnabled = transitionsEnabled;

  if (!scopeStore.listenerBound) {
    doc.addEventListener(
      "click",
      function (event) {
        const trigger =
          event.target && event.target.closest
            ? event.target.closest(
                'button[data-sl-vt-trigger="1"][data-sl-vt-scope="' + scope + '"]'
              )
            : null;
        if (!trigger) {
          return;
        }
        const sharedKey = String(trigger.getAttribute("data-sl-vt-shared-key") || "").trim();
        const sharedRole =
          String(trigger.getAttribute("data-sl-vt-shared-role") || "source").trim() === "target"
            ? "target"
            : "source";
        const sharedSnapshot = captureSharedSnapshot(sharedKey, sharedRole);
        writePending({
          scope: scope,
          action: String(trigger.getAttribute("data-sl-vt-action") || "toggle"),
          fromState: String(scopeStore.currentState || ""),
          createdAt: Date.now(),
          shared: sharedSnapshot,
        });
        setPhase("pending");
      },
      true
    );
    scopeStore.listenerBound = true;
  }

  const pending = readPending();
  const isPendingForScope = pending && pending.scope === scope;
  if (!isPendingForScope) {
    setPhase("idle");
    return;
  }

  const isStale = Math.abs(Date.now() - Number(pending.createdAt || 0)) > 5000;
  const fromState = String(pending.fromState || "");
  const stateChanged = !!currentState && !!fromState && currentState !== fromState;
  if (isStale || !stateChanged) {
    writePending(null);
    setPhase("idle");
    return;
  }

  if (!transitionsEnabled) {
    writePending(null);
    setPhase("idle");
    return;
  }

  parentWindow.requestAnimationFrame(function () {
    animateSharedToTarget(pending);
  });

  if (!nativeSupported) {
    setPhase("fallback-enter");
    root.classList.add("sl-vt-fallback-enter");
    parentWindow.setTimeout(function () {
      root.classList.remove("sl-vt-fallback-enter");
      setPhase("idle");
    }, durationMs + 40);
    writePending(null);
    return;
  }

  try {
    setPhase("running");
    const transition = doc.startViewTransition(function () {
      root.classList.add("sl-vt-native-enter");
    });
    transition.finished.finally(function () {
      root.classList.remove("sl-vt-native-enter");
      setPhase("idle");
    });
  } catch (error) {
    setPhase("fallback-enter");
    root.classList.add("sl-vt-fallback-enter");
    parentWindow.setTimeout(function () {
      root.classList.remove("sl-vt-fallback-enter");
      setPhase("idle");
    }, durationMs + 40);
  } finally {
    writePending(null);
  }
})();
</script>
""".replace("__CONFIG__", config_json)


def render_view_transition_layer(
    scope: str,
    *,
    current_state: str,
    enabled: bool = True,
    mobile_only: bool = True,
    duration_ms: int = 180,
) -> None:
    """Inject page-scoped list/detail transition helpers."""
    safe_scope = _normalize_token(scope, fallback="view-transition-scope")
    safe_state = _normalize_token(current_state, fallback="state")
    safe_duration = max(120, min(int(duration_ms), 300))

    st.markdown(_build_transition_style(safe_scope, duration_ms=safe_duration), unsafe_allow_html=True)
    st.markdown(
        (
            '<div data-sl-vt-root="1" '
            f'data-sl-vt-scope="{escape(safe_scope)}" '
            f'data-sl-vt-state="{escape(safe_state)}" '
            f'data-sl-vt-enabled="{1 if enabled else 0}" '
            f'data-sl-vt-mobile-only="{1 if mobile_only else 0}" '
            'aria-hidden="true"></div>'
        ),
        unsafe_allow_html=True,
    )
    config_json = json.dumps({"scope": safe_scope, "durationMs": safe_duration}, ensure_ascii=False)
    components.html(_build_transition_script(config_json), height=0)


def render_view_transition_trigger(
    scope: str,
    action: str,
    *,
    shared_key: object | None = None,
    shared_role: str = "source",
) -> None:
    """Insert an action marker that binds to the next rendered button."""
    safe_scope = _normalize_token(scope, fallback="view-transition-scope")
    safe_action = _normalize_token(action, fallback="toggle")
    safe_shared_key = _normalize_optional_token(shared_key)
    safe_shared_role = "target" if str(shared_role or "").strip().lower() == "target" else "source"
    shared_attrs = ""
    if safe_shared_key:
        shared_attrs = (
            f' data-sl-vt-shared-key="{escape(safe_shared_key)}" '
            f'data-sl-vt-shared-role="{escape(safe_shared_role)}"'
        )
    st.markdown(
        (
            '<span class="sl-vt-trigger-marker" data-sl-vt-trigger-marker="1" '
            f'data-sl-vt-scope="{escape(safe_scope)}" '
            f'data-sl-vt-action="{escape(safe_action)}" '
            f"{shared_attrs} "
            'aria-hidden="true"></span>'
        ),
        unsafe_allow_html=True,
    )


def render_view_transition_shared_element(scope: str, element_key: object | None, *, role: str = "source") -> None:
    """Insert a marker that binds to the next rendered visual element."""
    safe_scope = _normalize_token(scope, fallback="view-transition-scope")
    safe_key = _normalize_optional_token(element_key)
    if not safe_key:
        return
    safe_role = "target" if str(role or "").strip().lower() == "target" else "source"
    st.markdown(
        (
            '<span class="sl-vt-shared-marker" data-sl-vt-shared-marker="1" '
            f'data-sl-vt-scope="{escape(safe_scope)}" '
            f'data-sl-vt-shared-key="{escape(safe_key)}" '
            f'data-sl-vt-shared-role="{escape(safe_role)}" '
            'aria-hidden="true"></span>'
        ),
        unsafe_allow_html=True,
    )
