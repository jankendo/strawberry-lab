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


def _build_transition_style(scope: str, *, duration_ms: int) -> str:
    animation_name = f"sl-vt-enter-{scope}"
    return f"""
<style>
.sl-vt-trigger-marker,
[data-sl-vt-root] {{
    display: none !important;
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
  const storeKey = "__slViewTransitionStore";
  const pendingKey = "__slViewTransitionPending";
  const store = parentWindow[storeKey] || {};
  parentWindow[storeKey] = store;
  const scopeStore = store[scope] || {};
  store[scope] = scopeStore;

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
      let targetButton = null;
      for (let index = 0; index < buttons.length; index += 1) {
        const candidate = buttons[index];
        if (marker.compareDocumentPosition(candidate) & Node.DOCUMENT_POSITION_FOLLOWING) {
          targetButton = candidate;
          break;
        }
      }
      if (!targetButton) {
        return;
      }
      targetButton.setAttribute("data-sl-vt-trigger", "1");
      targetButton.setAttribute("data-sl-vt-scope", scope);
      targetButton.setAttribute("data-sl-vt-action", action);
    });
  }

  function getScopeMarker() {
    const markers = doc.querySelectorAll('[data-sl-vt-root][data-sl-vt-scope="' + scope + '"]');
    if (!markers.length) {
      return null;
    }
    return markers[markers.length - 1];
  }

  mapTriggerMarkers();
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
        writePending({
          scope: scope,
          action: String(trigger.getAttribute("data-sl-vt-action") || "toggle"),
          fromState: String(scopeStore.currentState || ""),
          createdAt: Date.now(),
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

  if (!nativeSupported) {
    setPhase("fallback-enter");
    root.classList.add("sl-vt-fallback-enter");
    parentWindow.setTimeout(function () {
      root.classList.remove("sl-vt-fallback-enter");
      setPhase("idle");
    }, Number(config.durationMs || 180) + 40);
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
    }, Number(config.durationMs || 180) + 40);
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


def render_view_transition_trigger(scope: str, action: str) -> None:
    """Insert an action marker that binds to the next rendered button."""
    safe_scope = _normalize_token(scope, fallback="view-transition-scope")
    safe_action = _normalize_token(action, fallback="toggle")
    st.markdown(
        (
            '<span class="sl-vt-trigger-marker" data-sl-vt-trigger-marker="1" '
            f'data-sl-vt-scope="{escape(safe_scope)}" '
            f'data-sl-vt-action="{escape(safe_action)}" '
            'aria-hidden="true"></span>'
        ),
        unsafe_allow_html=True,
    )
