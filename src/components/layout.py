"""Shared layout helpers for consistent UX."""

from __future__ import annotations

from html import unescape
import json
import os
import re

import streamlit as st
import streamlit.components.v1 as components

from src.components.offline_runtime import inject_offline_runtime
from src.components.tables import is_mobile_client

_BADGE_TONE_ALIASES = {
    "default": "neutral",
    "muted": "neutral",
    "ok": "success",
    "positive": "success",
    "warn": "warning",
    "caution": "warning",
    "error": "danger",
    "critical": "danger",
    "primary": "info",
    "accent": "info",
}

_BADGE_TONES = {"neutral", "success", "warning", "danger", "info"}

_BADGE_STYLE = {
    "neutral": {"icon": "◯"},
    "success": {"icon": "✅"},
    "warning": {"icon": "⚠️"},
    "danger": {"icon": "⛔"},
    "info": {"icon": "ℹ️"},
}

_SURFACE_TONE_ALIASES = {
    "default": "default",
    "neutral": "default",
    "soft": "soft",
    "muted": "soft",
    "accent": "accent",
    "brand": "accent",
    "warning": "warning",
    "danger": "danger",
}

_HTML_LINE_BREAK_RE = re.compile(r"(?i)<br\s*/?>")
_HTML_BLOCK_CLOSE_RE = re.compile(r"(?i)</(?:div|p|section|article|li|ul|ol|h[1-6])>")
_HTML_LIST_OPEN_RE = re.compile(r"(?i)<li[^>]*>")
_HTML_STRONG_OPEN_RE = re.compile(r"(?i)<(?:strong|b)>")
_HTML_STRONG_CLOSE_RE = re.compile(r"(?i)</(?:strong|b)>")
_HTML_TAG_RE = re.compile(r"(?is)<[^>]+>")
_NON_WORD_RE = re.compile(r"[^A-Za-z0-9_]+")
_PLACEHOLDER_VALUES = {"unknown", "none", "null", "-"}
_NATIVE_SHELL_CONFIG = {
    "app_title": "いちごDB",
    "theme_color": "#E8334A",
    "status_bar_style": "default",
}


def _as_bool(value: object | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "y"}:
        return True
    if normalized in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _should_hide_host_chrome() -> bool:
    try:
        secret_value = st.secrets.get("APP_HIDE_HOST_CHROME")
    except Exception:
        secret_value = None
    env_value = os.getenv("APP_HIDE_HOST_CHROME")
    if secret_value is not None:
        return _as_bool(secret_value, default=True)
    if env_value is not None:
        return _as_bool(env_value, default=True)
    return True


def _inject_native_shell_bootstrap() -> None:
    config_json = json.dumps(_NATIVE_SHELL_CONFIG, ensure_ascii=False)
    bootstrap_script = """
    <script>
    (function () {
      let parentWindow = null;
      let doc = null;
      try {
        parentWindow = window.parent;
        doc = parentWindow && parentWindow.document ? parentWindow.document : null;
      } catch (error) {
        console.warn("[native-shell] Unable to access parent document:", error);
        return;
      }
      if (!parentWindow || !doc || !doc.head) {
        return;
      }
      const config = __CONFIG_JSON__;
      const stateKey = "__slNativeShellState";
      const staticBaseCacheStorageKey = "__slNativeShellStaticBase";
      const state = parentWindow[stateKey] || {};
      parentWindow[stateKey] = state;

      function ensureMeta(name, content) {
        if (!name || !content) {
          return;
        }
        let element = doc.head.querySelector('meta[name="' + name + '"]');
        if (!element) {
          element = doc.createElement("meta");
          element.setAttribute("name", name);
          doc.head.appendChild(element);
        }
        element.setAttribute("content", content);
      }

      function ensureLink(rel, attrs) {
        if (!rel || !attrs || !attrs.href) {
          return;
        }
        let selector = 'link[rel="' + rel + '"]';
        if (attrs.sizes) {
          selector += '[sizes="' + attrs.sizes + '"]';
        }
        let element = doc.head.querySelector(selector);
        if (!element) {
          element = doc.createElement("link");
          element.setAttribute("rel", rel);
          doc.head.appendChild(element);
        }
        Object.keys(attrs).forEach(function (key) {
          if (attrs[key]) {
            element.setAttribute(key, attrs[key]);
          }
        });
      }

      function ensureViewportFitCover() {
        const viewportMeta = doc.head.querySelector('meta[name="viewport"]');
        if (!viewportMeta) {
          return;
        }
        const content = viewportMeta.getAttribute("content") || "";
        if (content.indexOf("viewport-fit=cover") !== -1) {
          return;
        }
        const normalized = content.trim();
        viewportMeta.setAttribute(
          "content",
          normalized
            ? normalized + ", viewport-fit=cover"
            : "width=device-width, initial-scale=1, viewport-fit=cover"
        );
      }

      function toAbsoluteUrl(pathValue) {
        if (!pathValue) {
          return "";
        }
        try {
          return new URL(pathValue, parentWindow.location.origin).href;
        } catch (error) {
          console.warn("[native-shell] Failed to build URL:", pathValue, error);
          return "";
        }
      }

      function detectBasePrefix() {
        const scripts = Array.prototype.slice.call(doc.querySelectorAll("script[src]"));
        for (let index = 0; index < scripts.length; index += 1) {
          const src = scripts[index].getAttribute("src") || "";
          if (src.indexOf("/static/") === -1 && src.indexOf("static/") !== 0) {
            continue;
          }
          try {
            const scriptUrl = new URL(src, parentWindow.location.href);
            const marker = "/static/";
            const markerIndex = scriptUrl.pathname.indexOf(marker);
            if (markerIndex >= 0) {
              return scriptUrl.pathname.slice(0, markerIndex + 1);
            }
          } catch (error) {
            console.warn("[native-shell] Failed to infer base prefix from script URL:", src, error);
          }
        }

        const pathname = parentWindow.location.pathname || "/";
        if (pathname === "/") {
          return "/";
        }
        if (pathname.endsWith("/")) {
          return pathname;
        }
        const lastSlash = pathname.lastIndexOf("/");
        if (lastSlash > 0) {
          return pathname.slice(0, lastSlash + 1);
        }
        return pathname + "/";
      }

      function buildStaticBaseCandidates() {
        const prefix = detectBasePrefix();
        const candidatePaths = [
          prefix + "app/static/",
          prefix + "static/",
          "/app/static/",
          "/static/",
        ];
        const uniqueCandidates = [];
        const seen = {};

        candidatePaths.forEach(function (candidatePath) {
          const absolute = toAbsoluteUrl(candidatePath);
          if (absolute && !seen[absolute]) {
            seen[absolute] = true;
            uniqueCandidates.push(absolute);
          }
        });
        return uniqueCandidates;
      }

      function getSessionStorage() {
        try {
          return parentWindow.sessionStorage || null;
        } catch (error) {
          console.warn("[native-shell] Unable to access sessionStorage:", error);
          return null;
        }
      }

      function readCachedStaticBase(candidateSignature) {
        if (!candidateSignature) {
          return null;
        }
        const storage = getSessionStorage();
        if (!storage) {
          return null;
        }
        try {
          const rawValue = storage.getItem(staticBaseCacheStorageKey);
          if (!rawValue) {
            return null;
          }
          const parsedValue = JSON.parse(rawValue);
          if (
            !parsedValue ||
            parsedValue.signature !== candidateSignature ||
            typeof parsedValue.url !== "string"
          ) {
            return null;
          }
          return parsedValue.url;
        } catch (error) {
          console.warn("[native-shell] Failed to read cached static base:", error);
          return null;
        }
      }

      function writeCachedStaticBase(candidateSignature, resolvedUrl) {
        if (!candidateSignature) {
          return;
        }
        const storage = getSessionStorage();
        if (!storage) {
          return;
        }
        try {
          storage.setItem(
            staticBaseCacheStorageKey,
            JSON.stringify({
              signature: candidateSignature,
              url: resolvedUrl || "",
            })
          );
        } catch (error) {
          console.warn("[native-shell] Failed to persist static base cache:", error);
        }
      }

      function chooseStaticBase(callback) {
        const candidates = buildStaticBaseCandidates();
        if (!candidates.length) {
          callback("");
          return;
        }
        const candidateSignature = candidates.join("|");
        if (
          state.staticBaseCandidatesSignature === candidateSignature &&
          typeof state.staticBaseUrl === "string"
        ) {
          callback(state.staticBaseUrl);
          return;
        }
        const cachedStaticBaseUrl = readCachedStaticBase(candidateSignature);
        if (cachedStaticBaseUrl !== null) {
          state.staticBaseUrl = cachedStaticBaseUrl;
          state.staticBaseCandidatesSignature = candidateSignature;
          state.staticBaseResolutionInFlight = false;
          callback(cachedStaticBaseUrl);
          return;
        }
        if (
          state.staticBaseResolutionInFlight &&
          state.staticBaseCandidatesSignature === candidateSignature
        ) {
          state.staticBaseCallbacks = state.staticBaseCallbacks || [];
          state.staticBaseCallbacks.push(callback);
          return;
        }
        const finalizeStaticBase = function (resolvedUrl) {
          state.staticBaseUrl = resolvedUrl || "";
          state.staticBaseCandidatesSignature = candidateSignature;
          state.staticBaseResolutionInFlight = false;
          writeCachedStaticBase(candidateSignature, state.staticBaseUrl);
          const pendingCallbacks = state.staticBaseCallbacks || [];
          state.staticBaseCallbacks = [];
          pendingCallbacks.forEach(function (pendingCallback) {
            try {
              pendingCallback(state.staticBaseUrl);
            } catch (error) {
              console.warn("[native-shell] Static base callback failed:", error);
            }
          });
        };
        state.staticBaseCandidatesSignature = candidateSignature;
        state.staticBaseResolutionInFlight = true;
        state.staticBaseCallbacks = [callback];
        if (!parentWindow.fetch) {
          finalizeStaticBase(candidates[0]);
          return;
        }

        let index = 0;
        const probeNext = function () {
          if (index >= candidates.length) {
            finalizeStaticBase(candidates[0]);
            return;
          }
          const candidate = candidates[index];
          index += 1;
          const manifestUrl = new URL("manifest.webmanifest", candidate).href;

          parentWindow
            .fetch(manifestUrl, {
              method: "GET",
              cache: "no-store",
              credentials: "same-origin",
            })
            .then(function (response) {
              if (response && response.ok) {
                finalizeStaticBase(candidate);
                return;
              }
              probeNext();
            })
            .catch(function (error) {
              console.warn("[native-shell] Failed to probe static candidate:", manifestUrl, error);
              probeNext();
            });
        };

        probeNext();
      }

      function ensureBottomNavRoot() {
        let root = doc.getElementById("sl-native-bottom-nav");
        if (!root) {
          root = doc.createElement("nav");
          root.id = "sl-native-bottom-nav";
          root.className = "sl-native-bottom-nav";
          root.setAttribute("aria-label", "主要ナビゲーション");
          root.hidden = true;
          doc.body.appendChild(root);
        }
        return root;
      }

      function ensureMobileTopBarRoot() {
        let root = doc.getElementById("sl-native-mobile-topbar");
        if (!root) {
          root = doc.createElement("header");
          root.id = "sl-native-mobile-topbar";
          root.className = "sl-native-mobile-topbar";
          root.setAttribute("aria-label", "モバイルメニュー");
          root.hidden = true;
          doc.body.appendChild(root);
        }
        return root;
      }

      function ensureMobileDrawerRoot() {
        let root = doc.getElementById("sl-native-mobile-drawer");
        if (!root) {
          root = doc.createElement("div");
          root.id = "sl-native-mobile-drawer";
          root.className = "sl-native-mobile-drawer";
          root.hidden = true;
          doc.body.appendChild(root);
        }
        return root;
      }

      function resolveNavigationHref(pathname) {
        const normalizedPath = String(pathname || "/").trim();
        const relativePath = normalizedPath === "/" ? "" : normalizedPath.replace(/^\\/+/, "");
        try {
          const prefix = detectBasePrefix();
          return new URL(relativePath, parentWindow.location.origin + prefix).href;
        } catch (error) {
          console.warn("[native-shell] Failed to resolve navigation href:", pathname, error);
          return "";
        }
      }

      function renderBottomNav(config) {
        const root = ensureBottomNavRoot();
        const items =
          config && Array.isArray(config.bottomItems)
            ? config.bottomItems
            : config && Array.isArray(config.items)
              ? config.items
              : [];
        if (!config || !config.visible || !items.length) {
          root.hidden = true;
          root.replaceChildren();
          doc.body.classList.remove("sl-has-native-bottom-nav");
          return;
        }

        root.hidden = false;
        root.replaceChildren();

        const list = doc.createElement("div");
        list.className = "sl-native-bottom-nav__list";

        items.forEach(function (item) {
          const isActive = item && item.key === config.activeKey;
          const control = doc.createElement("a");
          control.className = "sl-native-bottom-nav__item" + (isActive ? " is-active" : "");
          control.setAttribute("aria-label", (item && item.ariaLabel) || (item && item.label) || "");
          control.setAttribute("href", resolveNavigationHref(item && item.pathname));
          if (isActive) {
            control.setAttribute("aria-current", "page");
          }

          const icon = doc.createElement("span");
          icon.className = "sl-native-bottom-nav__icon";
          icon.textContent = item.icon || "";
          icon.setAttribute("aria-hidden", "true");

          const label = doc.createElement("span");
          label.className = "sl-native-bottom-nav__label";
          label.textContent = item.label || "";

          control.appendChild(icon);
          control.appendChild(label);
          list.appendChild(control);
        });

        root.appendChild(list);
        doc.body.classList.add("sl-has-native-bottom-nav");
      }

      function setMobileMenuOpen(isOpen) {
        state.mobileMenuOpen = !!isOpen;
        if (typeof state.renderMobileShell === "function") {
          state.renderMobileShell(state.mobileNavConfig || state.bottomNavConfig || null);
        }
      }

      function renderMobileShell(config) {
        const topBarRoot = ensureMobileTopBarRoot();
        const drawerRoot = ensureMobileDrawerRoot();
        const menuItems = config && Array.isArray(config.drawerItems) ? config.drawerItems : [];
        const visible = !!(config && config.visible && menuItems.length);

        if (!visible) {
          state.mobileMenuOpen = false;
          topBarRoot.hidden = true;
          topBarRoot.replaceChildren();
          drawerRoot.hidden = true;
          drawerRoot.replaceChildren();
          doc.body.classList.remove("sl-has-native-mobile-topbar");
          doc.body.classList.remove("sl-mobile-menu-open");
          return;
        }

        const activePageKey = String((config && config.activePageKey) || "");
        if (state.lastMobileShellActivePageKey !== activePageKey) {
          state.mobileMenuOpen = false;
          state.lastMobileShellActivePageKey = activePageKey;
        }

        const activeMenuItem =
          menuItems.find(function (item) {
            return item && item.active;
          }) || null;
        const titleText =
          (activeMenuItem && activeMenuItem.label) ||
          String((config && config.appTitle) || "");

        topBarRoot.hidden = false;
        topBarRoot.replaceChildren();

        const topBarInner = doc.createElement("div");
        topBarInner.className = "sl-native-mobile-topbar__inner";

        const menuButton = doc.createElement("button");
        menuButton.type = "button";
        menuButton.className = "sl-native-mobile-topbar__menu-button";
        menuButton.textContent = "☰";
        menuButton.setAttribute("aria-label", String((config && config.menuButtonLabel) || "メニューを開く"));
        menuButton.setAttribute("aria-expanded", state.mobileMenuOpen ? "true" : "false");
        menuButton.onclick = function () {
          setMobileMenuOpen(!state.mobileMenuOpen);
        };

        const title = doc.createElement("div");
        title.className = "sl-native-mobile-topbar__title";
        title.textContent = titleText;

        const titleSub = doc.createElement("div");
        titleSub.className = "sl-native-mobile-topbar__subtitle";
        titleSub.textContent = String((config && config.appTitle) || "");

        const titleStack = doc.createElement("div");
        titleStack.className = "sl-native-mobile-topbar__title-stack";
        titleStack.appendChild(title);
        if (titleSub.textContent && titleSub.textContent !== title.textContent) {
          titleStack.appendChild(titleSub);
        }

        topBarInner.appendChild(menuButton);
        topBarInner.appendChild(titleStack);
        topBarRoot.appendChild(topBarInner);

        drawerRoot.hidden = false;
        drawerRoot.replaceChildren();

        const scrim = doc.createElement("button");
        scrim.type = "button";
        scrim.className = "sl-native-mobile-drawer__scrim" + (state.mobileMenuOpen ? " is-open" : "");
        scrim.setAttribute("aria-label", "メニューを閉じる");
        scrim.hidden = !state.mobileMenuOpen;
        scrim.onclick = function () {
          setMobileMenuOpen(false);
        };

        const panel = doc.createElement("aside");
        panel.className = "sl-native-mobile-drawer__panel" + (state.mobileMenuOpen ? " is-open" : "");
        panel.setAttribute("aria-label", String((config && config.drawerLabel) || "サイトメニュー"));
        panel.setAttribute("aria-hidden", state.mobileMenuOpen ? "false" : "true");

        const panelHeader = doc.createElement("div");
        panelHeader.className = "sl-native-mobile-drawer__header";

        const panelTitle = doc.createElement("div");
        panelTitle.className = "sl-native-mobile-drawer__title";
        panelTitle.textContent = String((config && config.drawerLabel) || "サイトメニュー");

        const panelClose = doc.createElement("button");
        panelClose.type = "button";
        panelClose.className = "sl-native-mobile-drawer__close";
        panelClose.textContent = "✕";
        panelClose.setAttribute("aria-label", "メニューを閉じる");
        panelClose.onclick = function () {
          setMobileMenuOpen(false);
        };

        panelHeader.appendChild(panelTitle);
        panelHeader.appendChild(panelClose);

        const panelList = doc.createElement("nav");
        panelList.className = "sl-native-mobile-drawer__list";
        panelList.setAttribute("aria-label", String((config && config.drawerLabel) || "サイトメニュー"));

        menuItems.forEach(function (item) {
          const isActive = !!(item && item.active);
          const control = doc.createElement("a");
          control.className = "sl-native-mobile-drawer__item" + (isActive ? " is-active" : "");
          control.setAttribute("href", resolveNavigationHref(item && item.pathname));
          control.setAttribute("aria-label", (item && item.ariaLabel) || (item && item.label) || "");
          if (isActive) {
            control.setAttribute("aria-current", "page");
          }
          control.addEventListener("click", function () {
            state.mobileMenuOpen = false;
          });

          const icon = doc.createElement("span");
          icon.className = "sl-native-mobile-drawer__item-icon";
          icon.textContent = (item && item.icon) || "";
          icon.setAttribute("aria-hidden", "true");

          const label = doc.createElement("span");
          label.className = "sl-native-mobile-drawer__item-label";
          label.textContent = (item && item.label) || "";

          control.appendChild(icon);
          control.appendChild(label);
          panelList.appendChild(control);
        });

        panel.appendChild(panelHeader);
        panel.appendChild(panelList);
        drawerRoot.appendChild(scrim);
        drawerRoot.appendChild(panel);

        doc.body.classList.add("sl-has-native-mobile-topbar");
        doc.body.classList.toggle("sl-mobile-menu-open", !!state.mobileMenuOpen);
      }

      function isLocalhostHost(hostname) {
        const normalized = (hostname || "").toLowerCase();
        return (
          normalized === "localhost" ||
          normalized === "127.0.0.1" ||
          normalized === "[::1]" ||
          normalized.endsWith(".localhost")
        );
      }

      function canRegisterServiceWorker() {
        if (!parentWindow.navigator || !("serviceWorker" in parentWindow.navigator)) {
          return false;
        }
        const secureContext = parentWindow.isSecureContext || parentWindow.location.protocol === "https:";
        const localhost = isLocalhostHost(parentWindow.location.hostname);
        return secureContext || localhost;
      }

      function normalizeScopePath(pathname) {
        const text = String(pathname || "/").trim();
        if (!text) {
          return "/";
        }
        return text.endsWith("/") ? text : text + "/";
      }

      function resolveStaticScopePath(staticBaseUrl) {
        try {
          return normalizeScopePath(new URL("./", staticBaseUrl).pathname || "/");
        } catch (error) {
          return "/";
        }
      }

      function applyHeadEnhancements(staticBaseUrl) {
        if (!staticBaseUrl) {
          return;
        }
        const manifestUrl = new URL("manifest.webmanifest", staticBaseUrl).href;
        const icon180 = new URL("icons/icon-180.png", staticBaseUrl).href;
        const icon192 = new URL("icons/icon-192.png", staticBaseUrl).href;
        const icon512 = new URL("icons/icon-512.png", staticBaseUrl).href;

        ensureViewportFitCover();
        ensureMeta("theme-color", config.theme_color);
        ensureMeta("mobile-web-app-capable", "yes");
        ensureMeta("apple-mobile-web-app-capable", "yes");
        ensureMeta("apple-mobile-web-app-status-bar-style", config.status_bar_style);
        ensureMeta("apple-mobile-web-app-title", config.app_title);

        ensureLink("manifest", {
          href: manifestUrl,
        });
        ensureLink("apple-touch-icon", {
          href: icon180,
          sizes: "180x180",
          type: "image/png",
        });
        ensureLink("icon", {
          href: icon192,
          sizes: "192x192",
          type: "image/png",
        });
        ensureLink("icon", {
          href: icon512,
          sizes: "512x512",
          type: "image/png",
        });
      }

      function registerServiceWorker(staticBaseUrl) {
        if (!staticBaseUrl || !canRegisterServiceWorker()) {
          return;
        }
        const swUrl = new URL("app-sw.js", staticBaseUrl).href;
        const fallbackScope = resolveStaticScopePath(staticBaseUrl);
        const scopeCandidates = [fallbackScope];
        const scopeSignature = scopeCandidates.join("|");

        if (
          state.serviceWorkerRegistered &&
          state.serviceWorkerUrl === swUrl &&
          state.serviceWorkerScopeSignature === scopeSignature
        ) {
          return;
        }
        if (
          state.serviceWorkerRegistrationInFlight &&
          state.serviceWorkerUrl === swUrl &&
          state.serviceWorkerScopeSignature === scopeSignature
        ) {
          return;
        }

        const registerWithScope = function (index) {
          const scopeValue = scopeCandidates[index];
          return parentWindow.navigator.serviceWorker.register(swUrl, { scope: scopeValue }).catch(function (error) {
            if (index + 1 < scopeCandidates.length) {
              console.warn(
                "[native-shell] Service worker registration scope rejected, retrying fallback scope:",
                scopeValue,
                error
              );
              return registerWithScope(index + 1);
            }
            throw error;
          });
        };

        state.serviceWorkerRegistrationInFlight = true;
        state.serviceWorkerUrl = swUrl;
        state.serviceWorkerScopeSignature = scopeSignature;

        registerWithScope(0)
          .then(function (registration) {
            state.serviceWorkerRegistered = true;
            state.serviceWorkerScope = registration.scope;
            state.serviceWorkerRegistrationInFlight = false;
          })
          .catch(function (error) {
            state.serviceWorkerRegistered = false;
            state.serviceWorkerRegistrationInFlight = false;
            console.warn("[native-shell] Service worker registration failed:", error);
          });
      }

      function installIOSScrollGuard() {
        if (state.iosScrollGuardInstalled) {
          return;
        }
        const navigatorRef = parentWindow.navigator || {};
        const userAgent = navigatorRef.userAgent || "";
        const platform = navigatorRef.platform || "";
        const maxTouchPoints = navigatorRef.maxTouchPoints || 0;
        const isIOS =
          /iPad|iPhone|iPod/.test(userAgent) || (platform === "MacIntel" && maxTouchPoints > 1);

        if (!isIOS || !("ontouchstart" in parentWindow)) {
          return;
        }

        let touchStartY = 0;
        const touchStartHandler = function (event) {
          if (!event.touches || event.touches.length !== 1) {
            return;
          }
          touchStartY = event.touches[0].clientY;
        };
        const touchMoveHandler = function (event) {
          if (!event.touches || event.touches.length !== 1) {
            return;
          }
          const currentY = event.touches[0].clientY;
          const scrollingElement = doc.scrollingElement || doc.documentElement;
          if (!scrollingElement) {
            return;
          }
          const isPullingDown = currentY > touchStartY;
          const isAtTop = scrollingElement.scrollTop <= 0;
          if (isPullingDown && isAtTop) {
            event.preventDefault();
          }
        };

        doc.addEventListener("touchstart", touchStartHandler, { passive: true });
        doc.addEventListener("touchmove", touchMoveHandler, { passive: false });
        state.iosScrollGuardInstalled = true;
      }

      function installMobileDrawerDismissHandlers() {
        if (state.mobileDrawerDismissHandlersInstalled) {
          return;
        }
        doc.addEventListener("keydown", function (event) {
          if (event.key === "Escape" && state.mobileMenuOpen) {
            setMobileMenuOpen(false);
          }
        });
        state.mobileDrawerDismissHandlersInstalled = true;
      }

      state.renderBottomNav = renderBottomNav;
      state.renderMobileShell = renderMobileShell;
      installIOSScrollGuard();
      installMobileDrawerDismissHandlers();
      renderBottomNav(state.mobileNavConfig || state.bottomNavConfig || null);
      renderMobileShell(state.mobileNavConfig || state.bottomNavConfig || null);
      chooseStaticBase(function (staticBaseUrl) {
        applyHeadEnhancements(staticBaseUrl);
        registerServiceWorker(staticBaseUrl);
      });
    })();
    </script>
    """
    components.html(
        bootstrap_script.replace("__CONFIG_JSON__", config_json),
        height=0,
    )


def inject_app_style() -> None:
    """Inject product-oriented, neutral-first design tokens and component styles."""
    host_chrome_css = ""
    if _should_hide_host_chrome():
        host_chrome_scope = "body.sl-has-native-bottom-nav " if is_mobile_client() else ""
        host_chrome_css = f"""
        {host_chrome_scope}header[data-testid="stHeader"],
        {host_chrome_scope}[data-testid="stToolbar"],
        {host_chrome_scope}[data-testid="stDecoration"],
        {host_chrome_scope}[data-testid="stStatusWidget"],
        {host_chrome_scope}#MainMenu,
        {host_chrome_scope}button[kind="header"],
        {host_chrome_scope}button[kind="headerNoPadding"] {{
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }}
        """
    mobile_nav_css = ""
    if is_mobile_client():
        mobile_nav_css = """
        body.sl-has-native-bottom-nav [data-testid="stSidebar"] {
            display: none !important;
        }
        """

    style = """
    <style>
    :root {
        --sl-bg: #f6f8fb;
        --sl-surface: #ffffff;
        --sl-surface-soft: #f3f5f8;
        --sl-surface-muted: #edf1f6;
        --sl-primary: #e8334a;
        --sl-primary-strong: #b92338;
        --sl-text: #1f2937;
        --sl-heading: #111827;
        --sl-muted: #5b6472;
        --sl-border: #d7dde7;
        --sl-border-strong: #bcc6d6;
        --sl-success: #1f8a4c;
        --sl-warning: #b87400;
        --sl-danger: #c23535;
        --sl-info: #2f6feb;
        --sl-space-1: 0.5rem;   /* 8px */
        --sl-space-2: 1rem;     /* 16px */
        --sl-space-3: 1.5rem;   /* 24px */
        --sl-space-4: 2rem;     /* 32px */
        --sl-space-5: 2.5rem;   /* 40px */
        --sl-space-6: 3rem;     /* 48px */
        --sl-touch-target: 44px;
        --sl-touch-target-mobile: 48px;
        --sl-safe-top: env(safe-area-inset-top, 0px);
        --sl-safe-bottom: env(safe-area-inset-bottom, 0px);
        --sl-mobile-topbar-height: 3.35rem;
        --sl-mobile-nav-height: 5.35rem;
        --sl-mobile-drawer-width: min(84vw, 21rem);
        --sl-body-size: 0.95rem;
        --sl-caption-size: 0.84rem;
        --sl-mobile-gap: 0.72rem;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", "Segoe UI", "Hiragino Sans", "Noto Sans JP", sans-serif;
        letter-spacing: -0.01em;
    }
    [data-testid="stAppViewContainer"] {
        background: var(--sl-bg);
        color: var(--sl-text);
        -webkit-tap-highlight-color: transparent;
    }
    html,
    body {
        overscroll-behavior-y: none;
        overscroll-behavior-x: none;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        overscroll-behavior-y: contain;
        touch-action: manipulation;
    }
    @supports (-webkit-touch-callout: none) {
        html,
        body {
            min-height: -webkit-fill-available;
        }
        body {
            -webkit-overflow-scrolling: touch;
        }
    }
    .block-container {
        max-width: 1320px;
        padding-top: var(--sl-space-3);
        padding-bottom: var(--sl-space-5);
        padding-left: var(--sl-space-3);
        padding-right: var(--sl-space-3);
    }
    [data-testid="stVerticalBlock"] {
        gap: var(--sl-space-3);
    }

    h1 {
        font-size: clamp(2rem, 5.2vw, 2.45rem);
        line-height: 1.25;
        margin-top: var(--sl-space-1);
        margin-bottom: var(--sl-space-2);
    }
    h2 {
        font-size: clamp(1.42rem, 3.8vw, 1.78rem);
        line-height: 1.3;
        margin-bottom: var(--sl-space-2);
    }
    h3 {
        font-size: clamp(1.08rem, 2.8vw, 1.24rem);
        line-height: 1.35;
        margin-bottom: var(--sl-space-1);
    }
    h1, h2, h3, h4, h5, h6 {
        color: var(--sl-heading);
        letter-spacing: 0.01em;
    }
    p, label, [data-testid="stMarkdownContainer"] {
        color: var(--sl-text);
        font-size: clamp(0.92rem, 2.7vw, var(--sl-body-size));
        line-height: 1.6;
    }
    [data-testid="stCaptionContainer"] {
        color: var(--sl-muted);
        font-size: var(--sl-caption-size);
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--sl-surface);
        border: 1px solid var(--sl-border);
        border-radius: 12px;
        padding: var(--sl-space-2);
        margin-bottom: var(--sl-space-2);
        box-shadow: 0 2px 12px rgba(17, 24, 39, 0.04);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:focus-within {
        border-color: var(--sl-primary);
        box-shadow: 0 0 0 2px rgba(232, 51, 74, 0.16);
    }

    div[data-testid="stMetric"] {
        background: var(--sl-surface);
        border: 1px solid var(--sl-border);
        border-radius: 10px;
        padding: var(--sl-space-1) var(--sl-space-2);
    }
    div[data-testid="stMetricLabel"] {
        color: var(--sl-muted);
        font-size: 0.82rem;
    }
    div[data-testid="stMetricValue"] {
        color: var(--sl-heading);
        font-size: 1.4rem;
        font-weight: 700;
    }

    [data-testid="stButton"] > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button {
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        background: #ffffff;
        color: var(--sl-text);
        font-weight: 600;
        padding: 0 var(--sl-space-2);
        transition:
            border-color 0.2s ease,
            background-color 0.2s ease,
            box-shadow 0.2s ease,
            color 0.2s ease,
            transform 0.08s ease-out;
    }
    [data-testid="stButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        border-color: var(--sl-primary);
        background: #fef8f9;
    }
    [data-testid="stButton"] > button:focus-visible,
    [data-testid="stDownloadButton"] > button:focus-visible,
    [data-testid="stFormSubmitButton"] > button:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24);
        outline-offset: 2px;
    }
    [data-testid="stButton"] > button:active,
    [data-testid="stDownloadButton"] > button:active,
    [data-testid="stFormSubmitButton"] > button:active {
        transform: scale(0.985);
    }
    [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stFormSubmitButton"] > button[kind="primary"],
    [data-testid="stDownloadButton"] > button[kind="primary"] {
        background: var(--sl-primary);
        border-color: var(--sl-primary);
        color: #ffffff;
    }
    [data-testid="stButton"] > button[kind="primary"]:hover,
    [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover,
    [data-testid="stDownloadButton"] > button[kind="primary"]:hover {
        background: var(--sl-primary-strong);
        border-color: var(--sl-primary-strong);
        color: #ffffff;
    }
    [data-testid="stButton"] > button:disabled,
    [data-testid="stFormSubmitButton"] > button:disabled {
        background: var(--sl-surface-soft);
        color: var(--sl-muted);
        border-color: var(--sl-border);
    }

    a {
        color: var(--sl-info);
        text-decoration-thickness: 1.2px;
        text-underline-offset: 0.12em;
    }
    a[data-testid="stPageLink-NavLink"] {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        background: #ffffff;
        color: var(--sl-text);
        font-weight: 600;
        padding: 0 var(--sl-space-2);
        text-decoration: none;
        margin-bottom: var(--sl-space-1);
        transition: border-color 0.2s ease, background-color 0.2s ease;
    }
    a[data-testid="stPageLink-NavLink"]:hover {
        border-color: var(--sl-primary);
        background: #fef8f9;
    }
    a[data-testid="stPageLink-NavLink"]:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24);
        outline-offset: 2px;
    }

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="textarea"] > div {
        border-color: var(--sl-border-strong) !important;
        background: #ffffff !important;
        border-radius: 10px !important;
        min-height: var(--sl-touch-target);
    }
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea {
        background: #ffffff !important;
    }
    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: var(--sl-primary) !important;
        box-shadow: 0 0 0 2px rgba(232, 51, 74, 0.18) !important;
    }
    div[data-baseweb="input"] > div[data-invalid="true"],
    div[data-baseweb="select"] > div[data-invalid="true"],
    div[data-baseweb="textarea"] > div[data-invalid="true"] {
        border-color: var(--sl-danger) !important;
        background: #fff3f3 !important;
        box-shadow: 0 0 0 2px rgba(194, 53, 53, 0.16) !important;
    }

    [data-testid="stSlider"] [data-baseweb="slider"] {
        min-height: var(--sl-touch-target);
        padding: 0.72rem 0.35rem 0.24rem;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] > div > div {
        min-height: 0.5rem !important;
        border-radius: 999px !important;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] > div > div:first-child {
        background: #d0d8e6 !important;
    }
    [data-testid="stSlider"] [data-baseweb="slider"] > div > div > div {
        background: linear-gradient(90deg, var(--sl-primary), var(--sl-primary-strong)) !important;
        border-radius: 999px !important;
    }
    [data-testid="stSlider"] [role="slider"] {
        width: 1.55rem !important;
        height: 1.55rem !important;
        margin-top: -0.48rem !important;
        border: 3px solid #ffffff !important;
        background: var(--sl-primary) !important;
        box-shadow: 0 0 0 2px rgba(185, 35, 56, 0.22), 0 4px 10px rgba(17, 24, 39, 0.2) !important;
    }
    [data-testid="stSlider"] [role="slider"]:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24) !important;
        outline-offset: 2px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: var(--sl-space-1);
        margin-bottom: var(--sl-space-2);
    }
    .stTabs [data-baseweb="tab"] {
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        padding: 0 var(--sl-space-2);
        background: #ffffff;
        color: var(--sl-text);
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab"]:hover {
        border-color: var(--sl-primary);
        background: #fef8f9;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: var(--sl-primary);
        border-color: var(--sl-primary);
        color: #ffffff;
    }

    [data-testid="stSidebar"] {
        background: var(--sl-surface-soft);
        border-right: 1px solid var(--sl-border);
    }
    [data-testid="stSidebar"] .sl-sidebar-brand {
        border: 1px solid var(--sl-border);
        border-radius: 12px;
        background: #ffffff;
        padding: var(--sl-space-2);
        margin-bottom: var(--sl-space-2);
    }
    [data-testid="stSidebar"] .sl-sidebar-brand-title {
        color: var(--sl-heading);
        font-size: 1.02rem;
        font-weight: 700;
    }
    [data-testid="stSidebar"] .sl-sidebar-brand-sub {
        color: var(--sl-muted);
        font-size: 0.78rem;
    }
    [data-testid="stSidebar"] .sl-sidebar-active {
        display: flex;
        align-items: center;
        min-height: var(--sl-touch-target);
        border-radius: 10px;
        border: 1px solid var(--sl-primary);
        background: rgba(232, 51, 74, 0.1);
        color: var(--sl-heading);
        font-weight: 700;
        padding: 0 var(--sl-space-2);
        margin-bottom: var(--sl-space-1);
    }
    [data-testid="stSidebar"] .sl-sidebar-user {
        border: 1px solid var(--sl-border);
        border-radius: 12px;
        background: #ffffff;
        padding: var(--sl-space-2);
        margin-top: var(--sl-space-2);
    }
    .sl-native-mobile-topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 49;
        pointer-events: none;
    }
    .sl-native-mobile-topbar[hidden] {
        display: none !important;
    }
    .sl-native-mobile-topbar__inner {
        display: flex;
        align-items: center;
        gap: 0.72rem;
        min-height: calc(var(--sl-mobile-topbar-height) + var(--sl-safe-top));
        padding: calc(0.28rem + var(--sl-safe-top)) 0.82rem 0.38rem;
        background: linear-gradient(180deg, rgba(246, 248, 251, 0.96), rgba(246, 248, 251, 0.78));
        backdrop-filter: saturate(1.8) blur(18px);
        -webkit-backdrop-filter: saturate(1.8) blur(18px);
        border-bottom: 1px solid rgba(188, 198, 214, 0.55);
        pointer-events: auto;
    }
    .sl-native-mobile-topbar__menu-button {
        appearance: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2.7rem;
        min-width: 2.7rem;
        height: 2.7rem;
        border: 1px solid rgba(188, 198, 214, 0.78);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.9);
        color: var(--sl-heading);
        font: inherit;
        font-size: 1.15rem;
        font-weight: 700;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.1);
        cursor: pointer;
        transition: transform 0.08s ease-out, background-color 0.2s ease, border-color 0.2s ease;
    }
    .sl-native-mobile-topbar__menu-button:active {
        transform: scale(0.96);
        background: rgba(253, 242, 244, 0.96);
        border-color: rgba(232, 51, 74, 0.22);
    }
    .sl-native-mobile-topbar__menu-button:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24);
        outline-offset: 2px;
    }
    .sl-native-mobile-topbar__title-stack {
        display: flex;
        flex-direction: column;
        min-width: 0;
    }
    .sl-native-mobile-topbar__title {
        color: var(--sl-heading);
        font-size: 0.98rem;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .sl-native-mobile-topbar__subtitle {
        color: var(--sl-muted);
        font-size: 0.76rem;
        line-height: 1.2;
    }
    .sl-native-mobile-drawer {
        position: fixed;
        inset: 0;
        z-index: 52;
        pointer-events: none;
    }
    .sl-native-mobile-drawer[hidden] {
        display: none !important;
    }
    .sl-native-mobile-drawer__scrim {
        appearance: none;
        position: absolute;
        inset: 0;
        border: 0;
        background: rgba(15, 23, 42, 0.38);
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.22s ease;
    }
    .sl-native-mobile-drawer__scrim[hidden] {
        display: none !important;
    }
    .sl-native-mobile-drawer__scrim.is-open {
        opacity: 1;
        pointer-events: auto;
    }
    .sl-native-mobile-drawer__panel {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        width: var(--sl-mobile-drawer-width);
        max-width: 100%;
        padding: calc(0.8rem + var(--sl-safe-top)) 0.9rem calc(1rem + var(--sl-safe-bottom));
        background: rgba(248, 250, 252, 0.95);
        border-right: 1px solid rgba(188, 198, 214, 0.7);
        box-shadow: 20px 0 42px rgba(15, 23, 42, 0.18);
        backdrop-filter: saturate(1.8) blur(18px);
        -webkit-backdrop-filter: saturate(1.8) blur(18px);
        transform: translateX(calc(-100% - 1rem));
        transition: transform 0.22s ease;
        pointer-events: auto;
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
    }
    .sl-native-mobile-drawer__panel.is-open {
        transform: translateX(0);
    }
    .sl-native-mobile-drawer__header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
    }
    .sl-native-mobile-drawer__title {
        color: var(--sl-heading);
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .sl-native-mobile-drawer__close {
        appearance: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2.5rem;
        min-width: 2.5rem;
        height: 2.5rem;
        border: 1px solid rgba(188, 198, 214, 0.78);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.88);
        color: var(--sl-heading);
        font: inherit;
        font-size: 1rem;
        font-weight: 700;
        cursor: pointer;
    }
    .sl-native-mobile-drawer__close:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24);
        outline-offset: 2px;
    }
    .sl-native-mobile-drawer__list {
        display: flex;
        flex-direction: column;
        gap: 0.52rem;
    }
    .sl-native-mobile-drawer__item {
        display: flex;
        align-items: center;
        gap: 0.72rem;
        min-height: var(--sl-touch-target-mobile);
        border: 1px solid rgba(188, 198, 214, 0.78);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.88);
        color: var(--sl-text);
        text-decoration: none;
        font-weight: 650;
        padding: 0 0.92rem;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
    }
    .sl-native-mobile-drawer__item.is-active {
        border-color: rgba(232, 51, 74, 0.28);
        background: rgba(255, 245, 247, 0.96);
        color: var(--sl-heading);
    }
    .sl-native-mobile-drawer__item-icon {
        font-size: 1rem;
        line-height: 1;
        flex-shrink: 0;
    }
    .sl-native-mobile-drawer__item-label {
        min-width: 0;
    }
    .sl-native-bottom-nav {
        position: fixed;
        left: 0.72rem;
        right: 0.72rem;
        bottom: calc(var(--sl-safe-bottom) + 0.38rem);
        z-index: 48;
        pointer-events: none;
    }
    .sl-native-bottom-nav[hidden] {
        display: none !important;
    }
    .sl-native-bottom-nav__list {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.22rem;
        padding: 0.32rem;
        border: 1px solid rgba(255, 255, 255, 0.55);
        border-radius: 22px;
        background: rgba(248, 250, 252, 0.74);
        box-shadow: 0 18px 36px rgba(15, 23, 42, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.7);
        backdrop-filter: saturate(1.8) blur(20px);
        -webkit-backdrop-filter: saturate(1.8) blur(20px);
        pointer-events: auto;
    }
    .sl-native-bottom-nav__item {
        appearance: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.16rem;
        width: 100%;
        min-width: 0;
        min-height: 60px;
        border-radius: 18px;
        border: 1px solid transparent;
        background: transparent;
        color: var(--sl-muted);
        font: inherit;
        font-weight: 640;
        text-align: center;
        line-height: 1.12;
        padding: 0.28rem 0.15rem;
        box-sizing: border-box;
        text-decoration: none;
        transition:
            border-color 0.2s ease,
            background-color 0.2s ease,
            color 0.2s ease,
            transform 0.08s ease-out,
            box-shadow 0.2s ease;
        cursor: pointer;
    }
    .sl-native-bottom-nav__item:hover {
        border-color: rgba(232, 51, 74, 0.16);
        background: rgba(255, 255, 255, 0.42);
        color: var(--sl-heading);
    }
    .sl-native-bottom-nav__item:active {
        transform: scale(0.97);
        border-color: rgba(232, 51, 74, 0.22);
        background: rgba(253, 242, 244, 0.88);
    }
    .sl-native-bottom-nav__item:focus-visible {
        outline: 3px solid rgba(232, 51, 74, 0.24);
        outline-offset: 2px;
    }
    .sl-native-bottom-nav__item.is-active {
        border-color: rgba(232, 51, 74, 0.22);
        background: rgba(255, 255, 255, 0.56);
        color: var(--sl-heading);
        font-weight: 700;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.75);
    }
    .sl-native-bottom-nav__icon {
        font-size: 1rem;
        line-height: 1;
        flex-shrink: 0;
    }
    .sl-native-bottom-nav__label {
        display: block;
        width: 100%;
        max-width: 100%;
        font-size: 0.72rem;
        white-space: normal;
        overflow-wrap: anywhere;
        word-break: keep-all;
    }

    .sl-workspace-meta-row {
        margin-bottom: var(--sl-space-2);
    }
    .sl-meta-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        min-height: var(--sl-touch-target);
        padding: 0 var(--sl-space-1);
        border: 1px solid var(--sl-border-strong);
        border-radius: 10px;
        background: #ffffff;
        color: var(--sl-text);
        font-size: 0.86rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .sl-context-chip {
        display: inline-block;
        margin: 0 var(--sl-space-1) var(--sl-space-1) 0;
        padding: 0.24rem 0.62rem;
        border-radius: 999px;
        border: 1px solid var(--sl-border);
        background: var(--sl-surface-soft);
        color: var(--sl-muted);
        font-size: 0.84rem;
        font-weight: 600;
    }
    .sl-user-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        min-height: var(--sl-touch-target);
        padding: 0 var(--sl-space-1);
        border-radius: 10px;
        border: 1px solid var(--sl-border-strong);
        background: #ffffff;
        color: var(--sl-text);
        font-size: 0.84rem;
        font-weight: 600;
    }
    .sl-segmented-control-active {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        min-height: var(--sl-touch-target);
        padding: 0 var(--sl-space-2);
        border-radius: 999px;
        border: 1px solid rgba(232, 51, 74, 0.2);
        background: rgba(232, 51, 74, 0.1);
        color: var(--sl-heading);
        font-size: 0.92rem;
        font-weight: 700;
        text-align: center;
        box-sizing: border-box;
    }

    .sl-status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.28rem;
        border-radius: 999px;
        border: 1px solid transparent;
        padding: 0.2rem 0.58rem;
        font-size: 0.82rem;
        font-weight: 700;
    }

    @media (max-width: 820px) {
        .block-container {
            max-width: 100%;
            padding-top: calc(0.35rem + var(--sl-safe-top));
            padding-right: 0.82rem;
            padding-left: 0.82rem;
            padding-bottom: calc(1.35rem + var(--sl-safe-bottom));
        }
        body.sl-has-native-mobile-topbar .block-container {
            padding-top: calc(var(--sl-mobile-topbar-height) + var(--sl-safe-top) + 0.75rem);
        }
        body.sl-has-native-bottom-nav .block-container {
            padding-bottom: calc(var(--sl-mobile-nav-height) + 1.35rem + var(--sl-safe-bottom));
        }
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            padding-top: 0 !important;
        }
        [data-testid="stVerticalBlock"] {
            gap: var(--sl-mobile-gap);
        }
        h1 {
            font-size: 1.7rem;
            line-height: 1.3;
        }
        h2 {
            font-size: 1.38rem;
            line-height: 1.33;
        }
        h3 {
            font-size: 1.08rem;
        }
        p, label, [data-testid="stMarkdownContainer"] {
            font-size: 0.98rem;
            line-height: 1.52;
        }
        [data-testid="stCaptionContainer"] {
            font-size: 0.86rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            padding: 0.84rem;
            margin-bottom: var(--sl-mobile-gap);
        }
        [data-testid="stButton"] > button,
        [data-testid="stDownloadButton"] > button,
        [data-testid="stFormSubmitButton"] > button,
        .stTabs [data-baseweb="tab"],
        .sl-meta-chip,
        .sl-user-chip,
        .sl-segmented-control-active {
            min-height: var(--sl-touch-target-mobile);
            font-size: 0.98rem;
        }
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        div[data-baseweb="textarea"] > div {
            min-height: var(--sl-touch-target-mobile);
        }
        [data-testid="stSlider"] [data-baseweb="slider"] {
            min-height: calc(var(--sl-touch-target-mobile) + 4px);
            padding-top: 0.84rem;
        }
        [data-testid="stSlider"] [role="slider"] {
            width: 1.68rem !important;
            height: 1.68rem !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: var(--sl-mobile-gap) !important;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] > div {
            min-width: 100% !important;
            max-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        __MOBILE_NAV_CSS__
    }

    @media (prefers-reduced-motion: reduce) {
        [data-testid="stButton"] > button,
        [data-testid="stDownloadButton"] > button,
        [data-testid="stFormSubmitButton"] > button,
        .sl-native-bottom-nav__item,
        .sl-native-mobile-topbar__menu-button,
        .sl-native-mobile-drawer__scrim,
        .sl-native-mobile-drawer__panel {
            transition: none !important;
        }
    }
    .sl-status-neutral {
        color: #4b5563;
        background: #f3f4f6;
        border-color: #d1d5db;
    }
    .sl-status-success {
        color: #166534;
        background: #ecfdf3;
        border-color: #86efac;
    }
    .sl-status-warning {
        color: #92400e;
        background: #fffbeb;
        border-color: #fcd34d;
    }
    .sl-status-danger {
        color: #991b1b;
        background: #fef2f2;
        border-color: #fca5a5;
    }
    .sl-status-info {
        color: #1d4ed8;
        background: #eff6ff;
        border-color: #93c5fd;
    }

    [data-testid="stDataFrame"] thead tr th {
        background: var(--sl-surface-muted) !important;
        color: var(--sl-heading) !important;
    }
    [data-testid="stDataFrame"] tbody tr:hover td {
        background: #f8fbff !important;
    }

    __HOST_CHROME_CSS__
    </style>
    """
    st.markdown(
        style.replace("__HOST_CHROME_CSS__", host_chrome_css).replace("__MOBILE_NAV_CSS__", mobile_nav_css),
        unsafe_allow_html=True,
    )
    _inject_native_shell_bootstrap()
    inject_offline_runtime()


def _normalize_badge_tone(tone: str | None) -> str:
    normalized = (tone or "neutral").strip().lower()
    normalized = _BADGE_TONE_ALIASES.get(normalized, normalized)
    return normalized if normalized in _BADGE_TONES else "neutral"


def _normalize_surface_tone(tone: str | None) -> str:
    normalized = (tone or "default").strip().lower()
    return _SURFACE_TONE_ALIASES.get(normalized, "default")


def _collapse_lines(text: str) -> str:
    rows: list[str] = []
    last_was_blank = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(stripped)
            last_was_blank = False
            continue
        if not last_was_blank:
            rows.append("")
            last_was_blank = True
    return "\n".join(rows).strip()


def _prepare_html_like_text(value: object | None) -> str:
    text = str(value or "").replace("\r\n", "\n")
    text = _HTML_LINE_BREAK_RE.sub("\n", text)
    text = _HTML_BLOCK_CLOSE_RE.sub("\n", text)
    text = _HTML_LIST_OPEN_RE.sub("- ", text)
    return text


def _sanitize_text(value: object | None) -> str:
    text = _prepare_html_like_text(value)
    text = _HTML_TAG_RE.sub("", text)
    return _collapse_lines(unescape(text))


def _sanitize_markdown(value: object | None) -> str:
    text = _prepare_html_like_text(value)
    text = _HTML_STRONG_OPEN_RE.sub("**", text)
    text = _HTML_STRONG_CLOSE_RE.sub("**", text)
    text = _HTML_TAG_RE.sub("", text)
    return _collapse_lines(unescape(text))


def _keyify(value: object | None) -> str:
    raw = _sanitize_text(value).strip() or "default"
    return _NON_WORD_RE.sub("_", raw).strip("_").lower() or "default"


def _render_workspace_meta_controls(context: str) -> None:
    if not st.session_state.get("is_authenticated"):
        return

    user_email = _sanitize_text((st.session_state.get("current_user") or {}).get("email"))
    if user_email.strip().lower() in _PLACEHOLDER_VALUES:
        user_email = ""
    user_label = user_email or "アカウント"
    mobile_client = is_mobile_client()

    if mobile_client:
        title_col, action_col = st.columns([1.35, 1], gap="small")
        with title_col:
            st.caption("研究ワークスペース")
            st.markdown(
                f'<span class="sl-user-chip">👤 {user_label}</span>',
                unsafe_allow_html=True,
            )
        with action_col:
            st.page_link("pages/07_settings.py", label="⚙️ 設定", use_container_width=True)
        return

    left_space, controls_col = st.columns([1.6, 1.4], gap="small")
    with left_space:
        st.caption("研究ワークスペース")
    with controls_col:
        st.markdown('<div class="sl-workspace-meta-row"></div>', unsafe_allow_html=True)
        c1, c2 = st.columns([1, 2], gap="small")
        with c1:
            st.page_link("pages/07_settings.py", label="⚙️ 設定", use_container_width=True)
        with c2:
            st.markdown(
                f'<span class="sl-user-chip">👤 {user_label}</span>',
                unsafe_allow_html=True,
            )


def render_page_header(title: str, description: str) -> None:
    """Render consistent page title block."""
    with st.container(border=True):
        _render_workspace_meta_controls(title)
        st.markdown(f"## {_sanitize_text(title)}")
        st.write(_sanitize_text(description))


def render_section_switcher(
    options: list[str],
    *,
    key: str,
    title: str = "表示セクション",
    description: str | None = None,
    mobile_label: str | None = None,
) -> str:
    """Render a compact section switcher with desktop pills and mobile select."""
    if not options:
        raise ValueError("options must not be empty")

    active_value = str(st.session_state.get(key) or options[0])
    if active_value not in options:
        active_value = options[0]
        st.session_state[key] = active_value

    clean_title = _sanitize_text(title)
    clean_description = _sanitize_text(description)
    label_text = _sanitize_text(mobile_label) or clean_title or "表示を選択"

    with st.container(border=True):
        if clean_title:
            render_section_title(clean_title, clean_description or None)
        elif clean_description:
            st.caption(clean_description)

        if is_mobile_client():
            return str(
                st.selectbox(
                    label_text,
                    options,
                    index=options.index(active_value),
                    key=key,
                )
            )

        columns = st.columns(len(options), gap="small")
        for option_index, (column, option) in enumerate(zip(columns, options, strict=True)):
            clean_option = _sanitize_text(option)
            with column:
                if option == active_value:
                    st.markdown(
                        f'<div class="sl-segmented-control-active" aria-current="true">{clean_option}</div>',
                        unsafe_allow_html=True,
                    )
                    continue
                if st.button(
                    clean_option,
                    key=f"{key}__option__{option_index}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state[key] = option
                    st.rerun()

    return str(st.session_state.get(key) or active_value)


def render_hero_banner(
    title: str,
    description: str,
    *,
    eyebrow: str | None = None,
    chips: list[str] | None = None,
) -> None:
    """Render top hero block with only the essential title and summary."""
    _ = eyebrow, chips
    with st.container(border=True):
        _render_workspace_meta_controls(title)
        st.markdown(f"## {_sanitize_text(title)}")
        st.write(_sanitize_text(description))


def render_action_bar(
    actions: list[str] | None = None,
    *,
    title: str | None = None,
    description: str | None = None,
) -> None:
    """Keep backward compatibility for removed page-level action summaries."""
    _ = actions, title, description
    return


def render_sticky_primary_action_anchor(anchor_id: str) -> None:
    """Mark the next primary action so it can dock near the viewport bottom on mobile."""
    marker = _keyify(anchor_id)
    st.markdown(
        f'<div class="sl-sticky-primary-anchor" data-sl-sticky-anchor="{marker}" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def render_lead(text: str) -> None:
    """Render highlighted lead paragraph."""
    with st.container(border=True):
        st.write(_sanitize_markdown(text))


def render_section_title(title: str, description: str | None = None) -> None:
    """Render section heading and optional supporting text."""
    st.markdown(f"### {_sanitize_text(title)}")
    if description:
        st.caption(_sanitize_text(description))


def render_status_badge(label: str, tone: str = "neutral", *, icon: str | None = None) -> str:
    """Render status badge text and return rendered value."""
    tone_key = _normalize_badge_tone(tone)
    style = _BADGE_STYLE[tone_key]
    icon_text = _sanitize_text(icon) if icon else style["icon"]
    label_text = _sanitize_text(label)
    badge_text = f"{icon_text} {label_text}".strip()
    st.markdown(
        f'<span class="sl-status-badge sl-status-{tone_key}">{badge_text}</span>',
        unsafe_allow_html=True,
    )
    return badge_text


def render_surface(
    content: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    tone: str = "default",
    elevated: bool = False,
) -> None:
    """Render reusable section/card surface."""
    tone_class = _normalize_surface_tone(tone)
    clean_title = _sanitize_text(title)
    clean_subtitle = _sanitize_text(subtitle)
    clean_content = _sanitize_markdown(content)

    _ = elevated  # kept for backward compatibility
    with st.container(border=True):
        if tone_class in {"warning", "danger"}:
            label_map = {"warning": "注意", "danger": "警告"}
            tone_map = {"warning": "warning", "danger": "danger"}
            render_status_badge(label_map[tone_class], tone=tone_map[tone_class])
        if clean_title:
            st.markdown(f"**{clean_title}**")
        if clean_subtitle:
            st.caption(clean_subtitle)
        if clean_content:
            st.markdown(clean_content)


def render_kpi_cards(items: list[tuple[str, str, str | None]], *, per_row: int = 4) -> None:
    """Render compact KPI cards in wrapped rows."""
    if not items:
        return

    per_row = max(1, int(per_row or 4))
    for start in range(0, len(items), per_row):
        row_items = items[start : start + per_row]
        columns = st.columns(len(row_items))
        for column, (label, value, sub_text) in zip(columns, row_items, strict=True):
            with column:
                with st.container(border=True):
                    st.metric(_sanitize_text(label), _sanitize_text(value))
                    if sub_text:
                        st.caption(_sanitize_text(sub_text))


def render_info_card(text: str) -> None:
    """Render informational card block."""
    render_surface(text, tone="soft")


def render_empty_state(
    message: str,
    *,
    title: str = "表示できるデータがありません",
    hint: str | None = None,
    action_label: str | None = None,
    action_path: str | None = None,
) -> None:
    """Render empty state with optional next action."""
    sections = [_sanitize_markdown(message)]
    if hint:
        sections.append(_sanitize_markdown(hint))
    render_surface("\n\n".join(part for part in sections if part), title=title, tone="soft")
    if action_label and action_path:
        st.page_link(action_path, label=_sanitize_text(action_label), use_container_width=True)
