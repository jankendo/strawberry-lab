"""Client-side draft buffer helpers backed by localStorage."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

import streamlit.components.v1 as components

_DRAFT_KEY_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_FIELD_NAME_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_ALLOWED_FIELD_KINDS = {"text", "textarea", "number", "date", "select", "slider"}
_MAX_DRAFT_KEY_LENGTH = 96
_MAX_FIELD_NAME_LENGTH = 64
_MAX_FIELD_LABEL_LENGTH = 96


def _normalize_draft_key(value: object, *, fallback: str = "draft-buffer") -> str:
    text = _DRAFT_KEY_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_.:")
    if not text:
        return fallback
    return text[:_MAX_DRAFT_KEY_LENGTH]


def _normalize_fields(fields: Sequence[Mapping[str, object]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for field in fields:
        raw_name = _FIELD_NAME_SANITIZER_RE.sub("-", str(field.get("name") or "").strip()).strip("-_.:")
        label = str(field.get("label") or "").strip()
        kind = str(field.get("kind") or "text").strip().lower()
        if not raw_name or not label:
            continue
        if kind not in _ALLOWED_FIELD_KINDS:
            kind = "text"
        normalized.append(
            {
                "name": raw_name[:_MAX_FIELD_NAME_LENGTH],
                "label": label[:_MAX_FIELD_LABEL_LENGTH],
                "kind": kind,
            }
        )
    return normalized


def _build_script(config_json: str) -> str:
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

  const draftKey = String(config.draftKey || "").trim();
  if (!draftKey) {
    return;
  }

  function getStorage() {
    try {
      const storage = parentWindow.localStorage;
      if (!storage) {
        return null;
      }
      const probeKey = "__slDraftBufferProbe__";
      storage.setItem(probeKey, "1");
      storage.removeItem(probeKey);
      return storage;
    } catch (error) {
      return null;
    }
  }

  const storage = getStorage();
  if (!storage) {
    return;
  }

  const storageKey = "sl:draft-buffer:" + draftKey;
  const mode = String(config.mode || "get").toLowerCase();
  const fields = Array.isArray(config.fields) ? config.fields : [];
  const autosaveEnabled = config.autosave !== false;
  const clearBeforeRestore = !!config.clearBeforeRestore;
  const noticeMessage = String(
    config.noticeMessage || "保存前の下書きを復元しました。必要に応じて「下書きを破棄」を押してください。"
  );

  function readPayload() {
    try {
      const raw = storage.getItem(storageKey);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return null;
      }
      return parsed;
    } catch (error) {
      return null;
    }
  }

  function writePayload(payload) {
    try {
      if (!payload || typeof payload !== "object") {
        storage.removeItem(storageKey);
        return;
      }
      const keys = Object.keys(payload).filter(function (key) {
        return key !== "__updatedAt";
      });
      if (!keys.length) {
        storage.removeItem(storageKey);
        return;
      }
      storage.setItem(storageKey, JSON.stringify(payload));
    } catch (error) {
      // ignore storage failures
    }
  }

  function clearPayload() {
    try {
      storage.removeItem(storageKey);
    } catch (error) {
      // ignore storage failures
    }
  }

  function normalizeText(value) {
    return String(value || "")
      .replace(/[*＊]/g, "")
      .replace(/\s+/g, "")
      .trim()
      .toLowerCase();
  }

  function isVisible(node) {
    if (!node || !node.getBoundingClientRect) {
      return false;
    }
    const style = parentWindow.getComputedStyle ? parentWindow.getComputedStyle(node) : null;
    if (style && (style.display === "none" || style.visibility === "hidden")) {
      return false;
    }
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function findLabelRoot(targetLabel) {
    const normalizedTarget = normalizeText(targetLabel);
    if (!normalizedTarget) {
      return null;
    }
    const labels = Array.prototype.slice.call(doc.querySelectorAll("label"));
    for (let index = 0; index < labels.length; index += 1) {
      const label = labels[index];
      const normalizedLabel = normalizeText(label.textContent || "");
      if (!normalizedLabel) {
        continue;
      }
      if (
        normalizedLabel === normalizedTarget ||
        normalizedLabel.indexOf(normalizedTarget) !== -1 ||
        normalizedTarget.indexOf(normalizedLabel) !== -1
      ) {
        const widgetLabelRoot = label.closest('[data-testid="stWidgetLabel"]');
        if (widgetLabelRoot && widgetLabelRoot.parentElement) {
          return widgetLabelRoot.parentElement;
        }
        if (label.parentElement) {
          return label.parentElement;
        }
      }
    }
    return null;
  }

  function pickElementByKind(root, kind) {
    if (!root || !root.querySelector) {
      return null;
    }
    const loweredKind = String(kind || "text").toLowerCase();
    if (loweredKind === "textarea") {
      return root.querySelector("textarea");
    }
    if (loweredKind === "slider") {
      return root.querySelector('input[type="range"], [role="slider"]');
    }
    if (loweredKind === "select") {
      return root.querySelector('select, [role="combobox"], input[aria-haspopup="listbox"]');
    }
    if (loweredKind === "number") {
      return root.querySelector('input[type="number"], input[inputmode="decimal"], input[inputmode="numeric"]');
    }
    if (loweredKind === "date") {
      return root.querySelector('input[type="date"], input[placeholder*="YYYY"], input[placeholder*="年"]');
    }
    return root.querySelector('input:not([type="file"]), textarea, select');
  }

  function pickByAriaLabel(field) {
    const target = normalizeText(field.label || field.name || "");
    if (!target) {
      return null;
    }
    const candidates = Array.prototype.slice.call(
      doc.querySelectorAll('input:not([type="file"]), textarea, select, [role="combobox"], [role="slider"]')
    );
    for (let index = 0; index < candidates.length; index += 1) {
      const candidate = candidates[index];
      if (!isVisible(candidate)) {
        continue;
      }
      const ariaLabel = normalizeText(candidate.getAttribute("aria-label") || "");
      if (!ariaLabel) {
        continue;
      }
      if (ariaLabel === target || ariaLabel.indexOf(target) !== -1 || target.indexOf(ariaLabel) !== -1) {
        return candidate;
      }
    }
    return null;
  }

  function resolveFieldElement(field) {
    const byAria = pickByAriaLabel(field);
    if (byAria) {
      return byAria;
    }
    const root = findLabelRoot(field.label || field.name || "");
    if (!root) {
      return null;
    }
    const picked = pickElementByKind(root, field.kind || "text");
    if (picked && isVisible(picked)) {
      return picked;
    }
    return null;
  }

  function readFieldValue(element, kind) {
    if (!element) {
      return undefined;
    }
    const loweredKind = String(kind || "text").toLowerCase();
    if (loweredKind === "slider") {
      const ariaNow = element.getAttribute("aria-valuenow");
      if (ariaNow !== null && ariaNow !== "") {
        const numeric = Number(ariaNow);
        return Number.isFinite(numeric) ? numeric : ariaNow;
      }
    }
    if (element.tagName === "INPUT" || element.tagName === "TEXTAREA" || element.tagName === "SELECT") {
      if (loweredKind === "number") {
        const numeric = Number(element.value);
        return Number.isFinite(numeric) ? numeric : element.value;
      }
      return element.value;
    }
    if (element.getAttribute("role") === "combobox") {
      return element.value || element.textContent || "";
    }
    if (element.getAttribute("role") === "slider") {
      const sliderValue = element.getAttribute("aria-valuenow");
      const numeric = Number(sliderValue);
      return Number.isFinite(numeric) ? numeric : sliderValue || "";
    }
    return undefined;
  }

  function dispatchInputEvents(element) {
    if (!element || !element.dispatchEvent) {
      return;
    }
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
    element.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function setSliderValue(element, rawValue) {
    if (!element) {
      return;
    }
    if (element.tagName === "INPUT") {
      element.value = String(rawValue);
      dispatchInputEvents(element);
      return;
    }

    const target = Number(rawValue);
    const current = Number(element.getAttribute("aria-valuenow"));
    const step = Number(element.getAttribute("aria-valuestep") || 1) || 1;
    if (!Number.isFinite(target) || !Number.isFinite(current) || !step) {
      return;
    }
    if (Math.abs(target - current) < 1e-9) {
      return;
    }

    const direction = target > current ? "ArrowRight" : "ArrowLeft";
    const keySteps = Math.min(48, Math.max(1, Math.round(Math.abs(target - current) / Math.abs(step))));
    element.focus();
    for (let index = 0; index < keySteps; index += 1) {
      element.dispatchEvent(new KeyboardEvent("keydown", { key: direction, bubbles: true }));
      element.dispatchEvent(new KeyboardEvent("keyup", { key: direction, bubbles: true }));
    }
  }

  function setFieldValue(element, kind, value) {
    if (!element || value === undefined || value === null) {
      return false;
    }
    const loweredKind = String(kind || "text").toLowerCase();
    const nextValue = String(value);

    if (loweredKind === "slider") {
      setSliderValue(element, value);
      return true;
    }
    if (element.tagName === "INPUT" || element.tagName === "TEXTAREA" || element.tagName === "SELECT") {
      element.value = nextValue;
      dispatchInputEvents(element);
      return true;
    }
    if (element.getAttribute("role") === "combobox") {
      element.value = nextValue;
      dispatchInputEvents(element);
      return true;
    }
    return false;
  }

  function showNotice(message) {
    if (!message) {
      return;
    }
    const safeId = draftKey.replace(/[^A-Za-z0-9_-]/g, "-");
    const noticeId = "sl-draft-buffer-notice-" + safeId;
    let notice = doc.getElementById(noticeId);
    if (!notice) {
      notice = doc.createElement("div");
      notice.id = noticeId;
      notice.setAttribute("role", "status");
      notice.style.cssText =
        "margin:0.45rem 0 0.8rem;padding:0.48rem 0.72rem;border-radius:10px;border:1px solid #d7dde7;" +
        "background:rgba(47,111,235,0.08);color:#2b4a7f;font-size:0.82rem;line-height:1.4;";
      const host = doc.querySelector('[data-testid="stMainBlockContainer"]') || doc.body;
      if (host && host.firstChild) {
        host.insertBefore(notice, host.firstChild);
      } else if (host) {
        host.appendChild(notice);
      }
    }
    notice.textContent = message;
    notice.style.display = "block";
    if (instance.noticeTimer) {
      parentWindow.clearTimeout(instance.noticeTimer);
    }
    instance.noticeTimer = parentWindow.setTimeout(function () {
      if (notice) {
        notice.style.display = "none";
      }
    }, 5600);
  }

  function captureSnapshot() {
    const existing = readPayload() || {};
    const next = Object.assign({}, existing);
    let hasValue = false;
    let changed = false;

    fields.forEach(function (field) {
      const name = String(field.name || "").trim();
      if (!name) {
        return;
      }
      const element = resolveFieldElement(field);
      if (!element) {
        return;
      }
      const currentValue = readFieldValue(element, field.kind || "text");
      if (currentValue === undefined) {
        return;
      }
      hasValue = true;
      if (JSON.stringify(next[name]) !== JSON.stringify(currentValue)) {
        next[name] = currentValue;
        changed = true;
      }
    });

    if (!hasValue) {
      return;
    }
    if (!changed && next.__updatedAt) {
      return;
    }
    next.__updatedAt = Date.now();
    writePayload(next);
  }

  function restorePayload(payload) {
    if (!payload || typeof payload !== "object") {
      return 0;
    }
    const restoreValues = {};
    fields.forEach(function (field) {
      const name = String(field.name || "").trim();
      if (!name) {
        return;
      }
      if (Object.prototype.hasOwnProperty.call(payload, name)) {
        restoreValues[name] = payload[name];
      }
    });
    const restoreKeys = Object.keys(restoreValues);
    if (!restoreKeys.length) {
      return 0;
    }

    const signature = JSON.stringify(restoreValues);
    if (instance.lastRestoreSignature === signature) {
      return -1;
    }

    let restoredCount = 0;
    instance.applying = true;
    try {
      fields.forEach(function (field) {
        const name = String(field.name || "").trim();
        if (!name || !Object.prototype.hasOwnProperty.call(restoreValues, name)) {
          return;
        }
        const element = resolveFieldElement(field);
        if (!element) {
          return;
        }
        const didSet = setFieldValue(element, field.kind || "text", restoreValues[name]);
        if (didSet) {
          restoredCount += 1;
        }
      });
    } finally {
      instance.applying = false;
    }

    if (restoredCount > 0) {
      instance.lastRestoreSignature = signature;
    }
    return restoredCount;
  }

  if (mode === "clear") {
    clearPayload();
    return;
  }

  if (mode === "set") {
    const patch = config.payload && typeof config.payload === "object" ? config.payload : null;
    if (!patch) {
      clearPayload();
      return;
    }
    const current = readPayload() || {};
    const next = Object.assign({}, current, patch);
    next.__updatedAt = Date.now();
    writePayload(next);
    return;
  }

  if (!fields.length) {
    return;
  }

  const registryKey = "__slDraftBufferRegistry";
  const registry = parentWindow[registryKey] || {};
  parentWindow[registryKey] = registry;
  const instance = registry[draftKey] || {};
  registry[draftKey] = instance;
  instance.applying = false;

  if (clearBeforeRestore) {
    clearPayload();
  }

  if (autosaveEnabled && !instance.bound) {
    const listener = function () {
      if (instance.applying) {
        return;
      }
      if (instance.autosaveTimer) {
        parentWindow.clearTimeout(instance.autosaveTimer);
      }
      const debounceMs = Number(config.debounceMs || 220);
      instance.autosaveTimer = parentWindow.setTimeout(function () {
        captureSnapshot();
      }, Number.isFinite(debounceMs) ? Math.max(80, debounceMs) : 220);
    };
    doc.addEventListener("input", listener, true);
    doc.addEventListener("change", listener, true);
    instance.bound = true;
    instance.listener = listener;
  }

  if (clearBeforeRestore) {
    return;
  }

  const initialPayload = readPayload();
  if (!initialPayload) {
    return;
  }

  let attempts = 0;
  function attemptRestore() {
    attempts += 1;
    const restoredCount = restorePayload(initialPayload);
    if (restoredCount < 0) {
      return;
    }
    if (restoredCount > 0) {
      showNotice(noticeMessage);
      return;
    }
    if (attempts < 30) {
      parentWindow.setTimeout(attemptRestore, 140);
    }
  }
  attemptRestore();
})();
</script>
""".replace("__CONFIG__", config_json)


def _inject(config: Mapping[str, object]) -> None:
    config_json = json.dumps(config, ensure_ascii=False)
    components.html(_build_script(config_json), height=0)


def set_draft_buffer(draft_key: str, payload: Mapping[str, Any]) -> None:
    """Merge payload into the draft buffer entry for the given key."""
    _inject(
        {
            "mode": "set",
            "draftKey": _normalize_draft_key(draft_key),
            "payload": dict(payload),
        }
    )


def get_draft_buffer(
    draft_key: str,
    *,
    fields: Sequence[Mapping[str, object]],
    notice_message: str | None = None,
    clear_before_restore: bool = False,
) -> None:
    """Restore a draft buffer entry for the given key."""
    _inject(
        {
            "mode": "get",
            "draftKey": _normalize_draft_key(draft_key),
            "fields": _normalize_fields(fields),
            "autosave": False,
            "noticeMessage": str(notice_message or ""),
            "clearBeforeRestore": bool(clear_before_restore),
        }
    )


def clear_draft_buffer(draft_key: str) -> None:
    """Clear a draft buffer entry for the given key."""
    _inject(
        {
            "mode": "clear",
            "draftKey": _normalize_draft_key(draft_key),
        }
    )


def render_draft_buffer_bridge(
    draft_key: str,
    *,
    fields: Sequence[Mapping[str, object]],
    notice_message: str | None = None,
    clear_before_restore: bool = False,
    autosave: bool = True,
    debounce_ms: int = 220,
) -> None:
    """Inject draft buffer restore/autosave bridge."""
    _inject(
        {
            "mode": "get",
            "draftKey": _normalize_draft_key(draft_key),
            "fields": _normalize_fields(fields),
            "autosave": bool(autosave),
            "noticeMessage": str(notice_message or ""),
            "clearBeforeRestore": bool(clear_before_restore),
            "debounceMs": max(80, min(int(debounce_ms), 1200)),
        }
    )
