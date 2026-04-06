"""Swipe-action helpers for progressive mobile card actions."""

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


def _build_swipe_style(scope: str, *, mobile_max_width: int) -> str:
    return f"""
<style>
.sl-swipe-row-marker,
.sl-swipe-secondary-marker {{
    display: none !important;
}}

.sl-swipe-control {{
    display: none;
}}

@media (max-width: {mobile_max_width}px) {{
    div[data-sl-swipe-row="1"][data-sl-swipe-scope="{scope}"][data-sl-swipe-enhanced="1"] .sl-swipe-control {{
        margin-top: 0.38rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
    }}

    div[data-sl-swipe-row="1"][data-sl-swipe-scope="{scope}"][data-sl-swipe-enhanced="1"] .sl-swipe-toggle {{
        appearance: none;
        border: 1px solid #d1d5db;
        border-radius: 999px;
        background: #ffffff;
        color: #374151;
        font-size: 0.78rem;
        font-weight: 600;
        line-height: 1.1;
        padding: 0.24rem 0.64rem;
        min-height: 32px;
        cursor: pointer;
    }}

    div[data-sl-swipe-row="1"][data-sl-swipe-scope="{scope}"][data-sl-swipe-enhanced="1"] .sl-swipe-toggle:focus-visible {{
        outline: 2px solid #f472b6;
        outline-offset: 2px;
    }}

    div[data-sl-swipe-row="1"][data-sl-swipe-scope="{scope}"][data-sl-swipe-enhanced="1"] .sl-swipe-hint {{
        color: #6b7280;
        font-size: 0.78rem;
        line-height: 1.3;
        white-space: nowrap;
    }}

    div[data-sl-swipe-row="1"][data-sl-swipe-scope="{scope}"][data-sl-swipe-enhanced="1"] [data-sl-swipe-secondary-actions="1"] {{
        max-height: 0;
        opacity: 0;
        overflow: clip;
        pointer-events: none;
        transform: translateY(-0.25rem);
        margin-top: 0 !important;
        transition:
            max-height 180ms cubic-bezier(0.2, 0, 0.2, 1),
            opacity 180ms ease,
            transform 180ms ease;
    }}

    div[data-sl-swipe-row="1"][data-sl-swipe-scope="{scope}"].sl-swipe-open [data-sl-swipe-secondary-actions="1"] {{
        max-height: 96px;
        opacity: 1;
        pointer-events: auto;
        transform: translateY(0);
        margin-top: 0.45rem !important;
    }}
}}

@media (prefers-reduced-motion: reduce) {{
    div[data-sl-swipe-row="1"][data-sl-swipe-scope="{scope}"][data-sl-swipe-enhanced="1"] [data-sl-swipe-secondary-actions="1"] {{
        transition: none !important;
    }}
}}
</style>
"""


def _build_swipe_script(config_json: str) -> str:
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
  if (!parentWindow || !doc) {
    return;
  }

  const scope = String(config.scope || "").trim();
  if (!scope) {
    return;
  }
  const threshold = Math.max(28, Number(config.thresholdPx || 56));
  const mobileMaxWidth = Math.max(480, Number(config.mobileMaxWidth || 960));
  const storeKey = "__slSwipeActionStore";
  const store = parentWindow[storeKey] || {};
  parentWindow[storeKey] = store;
  const scopeStore = store[scope] || {};
  store[scope] = scopeStore;

  function isEnabled() {
    const viewport = parentWindow.innerWidth || doc.documentElement.clientWidth || 0;
    const coarsePointer = parentWindow.matchMedia
      ? parentWindow.matchMedia("(pointer: coarse)").matches
      : "ontouchstart" in parentWindow;
    return coarsePointer && viewport <= mobileMaxWidth;
  }

  function getRows() {
    return Array.prototype.slice.call(
      doc.querySelectorAll(
        'div[data-sl-swipe-row="1"][data-sl-swipe-scope="' + scope + '"]'
      )
    );
  }

  function getRow(rowId) {
    if (!rowId) {
      return null;
    }
    return doc.querySelector(
      'div[data-sl-swipe-row="1"][data-sl-swipe-scope="' +
        scope +
        '"][data-sl-swipe-row-id="' +
        rowId +
        '"]'
    );
  }

  function updateToggleState(row, expanded) {
    if (!row) {
      return;
    }
    const rowId = String(row.getAttribute("data-sl-swipe-row-id") || "");
    if (!rowId) {
      return;
    }
    const toggles = row.querySelectorAll(
      'button[data-sl-swipe-toggle="1"][data-sl-swipe-scope="' +
        scope +
        '"][data-sl-swipe-row-id="' +
        rowId +
        '"]'
    );
    toggles.forEach(function (toggle) {
      const openLabel = String(toggle.getAttribute("data-sl-swipe-open-label") || "操作を表示");
      const closeLabel = String(toggle.getAttribute("data-sl-swipe-close-label") || "操作を閉じる");
      toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      toggle.textContent = expanded ? closeLabel : openLabel;
    });
  }

  function setRowOpen(row, open) {
    if (!row) {
      return;
    }
    row.classList.toggle("sl-swipe-open", !!open);
    updateToggleState(row, !!open);
  }

  function closeAllRows(exceptRowId) {
    getRows().forEach(function (row) {
      const rowId = String(row.getAttribute("data-sl-swipe-row-id") || "");
      if (exceptRowId && rowId === exceptRowId) {
        return;
      }
      setRowOpen(row, false);
    });
  }

  function toggleRow(rowId) {
    const row = getRow(rowId);
    if (!row) {
      return;
    }
    const willOpen = !row.classList.contains("sl-swipe-open");
    if (willOpen) {
      closeAllRows(rowId);
    }
    setRowOpen(row, willOpen);
  }

  function openRow(rowId) {
    const row = getRow(rowId);
    if (!row) {
      return;
    }
    closeAllRows(rowId);
    setRowOpen(row, true);
  }

  function closestElementContainer(node) {
    let current = node;
    while (current && current !== doc.body) {
      if (current.classList && current.classList.contains("element-container")) {
        return current;
      }
      current = current.parentElement;
    }
    return null;
  }

  function findNextActionBlock(marker) {
    const markerContainer = closestElementContainer(marker);
    if (!markerContainer) {
      return null;
    }
    let cursor = markerContainer.nextElementSibling;
    while (cursor) {
      if (cursor.querySelector('[data-sl-swipe-row-marker="1"]')) {
        break;
      }
      const horizontal = cursor.matches('[data-testid="stHorizontalBlock"]')
        ? cursor
        : cursor.querySelector('[data-testid="stHorizontalBlock"]');
      if (horizontal) {
        return horizontal;
      }
      const buttonBlock = cursor.querySelector('[data-testid="stButton"]');
      if (buttonBlock) {
        return buttonBlock;
      }
      cursor = cursor.nextElementSibling;
    }
    return null;
  }

  function isInteractiveTarget(target) {
    if (!target || !target.closest) {
      return false;
    }
    return !!target.closest(
      'button, a, input, select, textarea, label, [role="button"], [role="link"], [contenteditable="true"]'
    );
  }

  function bindRows() {
    const enabled = isEnabled();
    scopeStore.enabled = enabled;

    const rowMarkers = doc.querySelectorAll(
      '[data-sl-swipe-row-marker="1"][data-sl-swipe-scope="' + scope + '"]'
    );
    rowMarkers.forEach(function (marker) {
      const rowId = String(marker.getAttribute("data-sl-swipe-row-id") || "");
      const row = marker.closest('div[data-testid="stVerticalBlockBorderWrapper"]');
      if (!row || !rowId) {
        return;
      }
      row.setAttribute("data-sl-swipe-row", "1");
      row.setAttribute("data-sl-swipe-scope", scope);
      row.setAttribute("data-sl-swipe-row-id", rowId);
      if (enabled) {
        row.setAttribute("data-sl-swipe-enhanced", "1");
      } else {
        row.removeAttribute("data-sl-swipe-enhanced");
        setRowOpen(row, false);
      }
      updateToggleState(row, row.classList.contains("sl-swipe-open"));
    });

    const actionMarkers = doc.querySelectorAll(
      '[data-sl-swipe-secondary-marker="1"][data-sl-swipe-scope="' + scope + '"]'
    );
    actionMarkers.forEach(function (marker) {
      const rowId = String(marker.getAttribute("data-sl-swipe-row-id") || "");
      const actionBlock = findNextActionBlock(marker);
      if (!actionBlock || !rowId) {
        return;
      }
      actionBlock.setAttribute("data-sl-swipe-secondary-actions", "1");
      actionBlock.setAttribute("data-sl-swipe-scope", scope);
      actionBlock.setAttribute("data-sl-swipe-row-id", rowId);
    });
  }

  function bindGlobalListeners() {
    if (scopeStore.listenersBound) {
      return;
    }

    doc.addEventListener(
      "click",
      function (event) {
        const toggle =
          event.target && event.target.closest
            ? event.target.closest(
                'button[data-sl-swipe-toggle="1"][data-sl-swipe-scope="' + scope + '"]'
              )
            : null;
        if (!toggle) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        const rowId = String(toggle.getAttribute("data-sl-swipe-row-id") || "");
        toggleRow(rowId);
      },
      true
    );

    doc.addEventListener(
      "click",
      function (event) {
        if (!scopeStore.enabled) {
          return;
        }
        const target = event.target;
        if (
          target &&
          target.closest &&
          target.closest('div[data-sl-swipe-row="1"][data-sl-swipe-scope="' + scope + '"]')
        ) {
          return;
        }
        closeAllRows();
      },
      true
    );

    doc.addEventListener(
      "touchstart",
      function (event) {
        if (!scopeStore.enabled || !event.touches || event.touches.length !== 1) {
          scopeStore.activeTouch = null;
          return;
        }
        const target = event.target;
        if (!target || !target.closest) {
          scopeStore.activeTouch = null;
          return;
        }
        const row = target.closest(
          'div[data-sl-swipe-row="1"][data-sl-swipe-scope="' + scope + '"]'
        );
        if (!row || isInteractiveTarget(target)) {
          scopeStore.activeTouch = null;
          return;
        }
        const rowId = String(row.getAttribute("data-sl-swipe-row-id") || "");
        const touch = event.touches[0];
        scopeStore.activeTouch = {
          rowId: rowId,
          startX: touch.clientX,
          startY: touch.clientY,
          dx: 0,
          dy: 0,
          axis: "",
        };
      },
      { passive: true, capture: true }
    );

    doc.addEventListener(
      "touchmove",
      function (event) {
        const active = scopeStore.activeTouch;
        if (!scopeStore.enabled || !active || !event.touches || event.touches.length !== 1) {
          return;
        }
        const touch = event.touches[0];
        const dx = touch.clientX - Number(active.startX || 0);
        const dy = touch.clientY - Number(active.startY || 0);
        active.dx = dx;
        active.dy = dy;
        if (!active.axis) {
          if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
            return;
          }
          active.axis = Math.abs(dx) > Math.abs(dy) * 1.2 ? "x" : "y";
        }
      },
      { passive: true, capture: true }
    );

    doc.addEventListener(
      "touchend",
      function () {
        const active = scopeStore.activeTouch;
        scopeStore.activeTouch = null;
        if (!scopeStore.enabled || !active || active.axis !== "x") {
          return;
        }
        if (!active.rowId) {
          return;
        }
        if (Number(active.dx || 0) <= -threshold) {
          openRow(active.rowId);
          return;
        }
        if (Number(active.dx || 0) >= threshold * 0.6) {
          const row = getRow(active.rowId);
          if (row) {
            setRowOpen(row, false);
          }
        }
      },
      true
    );

    parentWindow.addEventListener("resize", function () {
      bindRows();
    });

    scopeStore.listenersBound = true;
  }

  bindGlobalListeners();
  bindRows();
})();
</script>
""".replace("__CONFIG__", config_json)


def render_swipe_action_layer(
    scope: str,
    *,
    threshold_px: int = 64,
    mobile_max_width: int = 960,
) -> None:
    """Inject scoped swipe-action behavior for touch devices."""
    safe_scope = _normalize_token(scope, fallback="swipe-actions")
    safe_threshold = max(32, min(int(threshold_px), 160))
    safe_width = max(480, min(int(mobile_max_width), 1400))
    st.markdown(_build_swipe_style(safe_scope, mobile_max_width=safe_width), unsafe_allow_html=True)
    config_json = json.dumps(
        {
            "scope": safe_scope,
            "thresholdPx": safe_threshold,
            "mobileMaxWidth": safe_width,
        },
        ensure_ascii=False,
    )
    components.html(_build_swipe_script(config_json), height=0)


def render_swipe_action_row_marker(
    scope: str,
    row_id: str,
    *,
    hint: str = "左にスワイプでクイック操作を表示",
    reveal_label: str = "操作を表示",
    hide_label: str = "操作を閉じる",
) -> None:
    """Mark a card row as swipe-capable and render explicit reveal control."""
    safe_scope = _normalize_token(scope, fallback="swipe-actions")
    safe_row_id = _normalize_token(row_id, fallback="row")
    st.markdown(
        (
            '<span class="sl-swipe-row-marker" data-sl-swipe-row-marker="1" '
            f'data-sl-swipe-scope="{escape(safe_scope)}" '
            f'data-sl-swipe-row-id="{escape(safe_row_id)}" aria-hidden="true"></span>'
            '<div class="sl-swipe-control">'
            '<button type="button" class="sl-swipe-toggle" data-sl-swipe-toggle="1" '
            f'data-sl-swipe-scope="{escape(safe_scope)}" '
            f'data-sl-swipe-row-id="{escape(safe_row_id)}" '
            f'data-sl-swipe-open-label="{escape(reveal_label)}" '
            f'data-sl-swipe-close-label="{escape(hide_label)}" '
            'aria-expanded="false">'
            f"{escape(reveal_label)}"
            "</button>"
            f'<span class="sl-swipe-hint">{escape(hint)}</span>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_swipe_action_secondary_marker(scope: str, row_id: str) -> None:
    """Mark the next block as a swipe-revealed secondary action area."""
    safe_scope = _normalize_token(scope, fallback="swipe-actions")
    safe_row_id = _normalize_token(row_id, fallback="row")
    st.markdown(
        (
            '<span class="sl-swipe-secondary-marker" data-sl-swipe-secondary-marker="1" '
            f'data-sl-swipe-scope="{escape(safe_scope)}" '
            f'data-sl-swipe-row-id="{escape(safe_row_id)}" '
            'aria-hidden="true"></span>'
        ),
        unsafe_allow_html=True,
    )
