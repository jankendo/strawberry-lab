"""Hidden bridge for syncing auth cookies in the parent browser document."""

from __future__ import annotations

import json

import streamlit.components.v1 as components

from src.services.auth_service import get_pending_auth_cookie_action


def render_auth_cookie_bridge_if_needed() -> None:
    """Render a hidden script that syncs the auth cookie in the top-level document."""
    action = get_pending_auth_cookie_action()
    if not action:
        return
    action_json = json.dumps(action, ensure_ascii=False)
    components.html(
        """
        <script>
        (function () {
          const action = __AUTH_COOKIE_ACTION__;
          if (!action || !action.type || !action.cookie_name) {
            return;
          }
          let parentWindow = null;
          let doc = null;
          try {
            parentWindow = window.parent;
            doc = parentWindow && parentWindow.document ? parentWindow.document : null;
          } catch (error) {
            console.warn("[auth-cookie-bridge] Unable to access parent window:", error);
            return;
          }
          if (!parentWindow || !doc) {
            return;
          }
          const markerKey = "__slAuthCookieBridge:" + String(action.id || "");
          let storage = null;
          try {
            storage = parentWindow.sessionStorage || null;
          } catch (error) {
            storage = null;
          }
          if (storage && storage.getItem(markerKey) === "done") {
            return;
          }
          if (storage) {
            storage.setItem(markerKey, "done");
          }
          const secureAttr = parentWindow.location.protocol === "https:" ? "; Secure" : "";
          if (action.type === "clear") {
            doc.cookie =
              String(action.cookie_name) +
              "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=Lax" +
              secureAttr;
          } else {
            const expiresAt = Number(action.expires_at || 0);
            const expiresUtc = expiresAt ? new Date(expiresAt * 1000).toUTCString() : "";
            doc.cookie =
              String(action.cookie_name) +
              "=" +
              encodeURIComponent(String(action.cookie_value || "")) +
              "; Path=/; SameSite=Lax" +
              secureAttr +
              (expiresUtc ? "; Expires=" + expiresUtc : "");
          }
          parentWindow.setTimeout(function () {
            parentWindow.location.reload();
          }, 0);
        })();
        </script>
        """.replace("__AUTH_COOKIE_ACTION__", action_json),
        height=0,
    )
