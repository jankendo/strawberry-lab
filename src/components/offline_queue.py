"""Client-side offline save-intent queue bridge backed by IndexedDB."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

import streamlit.components.v1 as components

_QUEUE_KEY_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_INTENT_ID_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_EVENT_NAME_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._:-]+")
_MAX_QUEUE_KEY_LENGTH = 96
_MAX_INTENT_ID_LENGTH = 96
_MAX_INTENT_TYPE_LENGTH = 64
_MAX_EVENT_NAME_LENGTH = 96
_DEFAULT_REPLAY_EVENT_NAME = "ichigodb:offline-intent-queue-replay-request"


def _normalize_queue_key(value: object, *, fallback: str = "offline-intent-queue") -> str:
    text = _QUEUE_KEY_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_.:")
    if not text:
        text = fallback
    return text[:_MAX_QUEUE_KEY_LENGTH]


def _normalize_intent_id(value: object, *, fallback: str | None = None) -> str:
    text = _INTENT_ID_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_.:")
    if not text:
        text = _INTENT_ID_SANITIZER_RE.sub("-", str(fallback or "").strip()).strip("-_.:")
    if not text:
        text = f"intent-{uuid4()}"
    return text[:_MAX_INTENT_ID_LENGTH]


def _normalize_event_name(value: object, *, fallback: str = _DEFAULT_REPLAY_EVENT_NAME) -> str:
    text = _EVENT_NAME_SANITIZER_RE.sub("-", str(value or "").strip()).strip("-_.:")
    if not text:
        text = _EVENT_NAME_SANITIZER_RE.sub("-", str(fallback or "").strip()).strip("-_.:")
    if not text:
        text = _DEFAULT_REPLAY_EVENT_NAME
    return text[:_MAX_EVENT_NAME_LENGTH]


def _safe_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def _build_script(config_json: str) -> str:
    return """
<script>
(async function () {
  try {
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

    const queueKey = String(config.queueKey || "").trim();
    if (!queueKey) {
      return;
    }

    const DEFAULT_REPLAY_EVENT_NAME = "ichigodb:offline-intent-queue-replay-request";
    const STORE_NAME = "save_intents";
    const DB_NAME = "ichigodb-offline-intent-queue";
    const DB_VERSION = 1;
    const NOTICE_STYLE_ID = "sl-offline-intent-queue-style";
    const runtimeKey = "__ichigodbOfflineIntentQueueRuntime";
    const runtime = parentWindow[runtimeKey] || {};
    parentWindow[runtimeKey] = runtime;
    runtime.instances = runtime.instances || {};
    runtime.operationChains = runtime.operationChains || {};
    runtime.memoryQueues = runtime.memoryQueues || {};
    runtime.storageProbe = runtime.storageProbe || { checked: false, available: null };

    function queueRuntimeOperation(targetQueueKey, operation) {
      const normalizedQueueKey = String(targetQueueKey || "").trim();
      if (!normalizedQueueKey || typeof operation !== "function") {
        return Promise.resolve(null);
      }
      const previous = runtime.operationChains[normalizedQueueKey] || Promise.resolve();
      const current = Promise.resolve(previous)
        .catch(function () {
          return null;
        })
        .then(function () {
          return operation();
        });
      runtime.operationChains[normalizedQueueKey] = current;
      return current.finally(function () {
        if (runtime.operationChains[normalizedQueueKey] === current) {
          delete runtime.operationChains[normalizedQueueKey];
        }
      });
    }

    function safeParse(rawValue, fallback) {
      if (rawValue === null || rawValue === undefined || rawValue === "") {
        return fallback;
      }
      try {
        return JSON.parse(rawValue);
      } catch (error) {
        return fallback;
      }
    }

    function normalizeQueueRows(rows, targetQueueKey) {
      if (!Array.isArray(rows)) {
        return [];
      }
      const normalized = [];
      rows.forEach(function (row) {
        if (!row || typeof row !== "object") {
          return;
        }
        const rowId = String(row.id || "").trim();
        const rowQueueKey = String(row.queueKey || "").trim();
        if (!rowId || rowQueueKey !== targetQueueKey) {
          return;
        }
        const payload = row.payload && typeof row.payload === "object" ? row.payload : {};
        const metadata = row.metadata && typeof row.metadata === "object" ? row.metadata : {};
        const createdAt = Number(row.createdAt);
        const updatedAt = Number(row.updatedAt);
        normalized.push({
          id: rowId,
          queueKey: rowQueueKey,
          intentType: String(row.intentType || "save"),
          payload: payload,
          metadata: metadata,
          status: String(row.status || "pending"),
          createdAt: Number.isFinite(createdAt) ? createdAt : Date.now(),
          updatedAt: Number.isFinite(updatedAt) ? updatedAt : Date.now(),
        });
      });
      normalized.sort(function (left, right) {
        return Number(left.createdAt || 0) - Number(right.createdAt || 0);
      });
      return normalized;
    }

    function getStorage() {
      if (runtime.storageProbe.checked) {
        return runtime.storageProbe.available ? parentWindow.localStorage : null;
      }
      runtime.storageProbe.checked = true;
      try {
        const storage = parentWindow.localStorage;
        if (!storage) {
          runtime.storageProbe.available = false;
          return null;
        }
        const probeKey = "__slOfflineIntentQueueProbe__";
        storage.setItem(probeKey, "1");
        storage.removeItem(probeKey);
        runtime.storageProbe.available = true;
        return storage;
      } catch (error) {
        runtime.storageProbe.available = false;
        return null;
      }
    }

    function localStorageKey(targetQueueKey) {
      return "sl:offline-intent-queue:" + targetQueueKey;
    }

    function readLocalQueue(targetQueueKey) {
      const storage = getStorage();
      if (!storage) {
        const memoryRows = runtime.memoryQueues[targetQueueKey];
        return normalizeQueueRows(memoryRows, targetQueueKey);
      }
      try {
        const parsed = safeParse(storage.getItem(localStorageKey(targetQueueKey)), []);
        return normalizeQueueRows(parsed, targetQueueKey);
      } catch (error) {
        return [];
      }
    }

    function writeLocalQueue(targetQueueKey, rows) {
      const normalizedRows = normalizeQueueRows(rows, targetQueueKey);
      const storage = getStorage();
      if (!storage) {
        runtime.memoryQueues[targetQueueKey] = normalizedRows;
        return;
      }
      try {
        if (!normalizedRows.length) {
          storage.removeItem(localStorageKey(targetQueueKey));
          return;
        }
        storage.setItem(localStorageKey(targetQueueKey), JSON.stringify(normalizedRows));
      } catch (error) {
        runtime.memoryQueues[targetQueueKey] = normalizedRows;
      }
    }

    function normalizeIntent(targetQueueKey, rawIntent) {
      const candidate = rawIntent && typeof rawIntent === "object" ? rawIntent : {};
      const now = Date.now();
      const createdAt = Number(candidate.createdAt);
      const updatedAt = Number(candidate.updatedAt);
      const payload = candidate.payload && typeof candidate.payload === "object" ? candidate.payload : {};
      const metadata = candidate.metadata && typeof candidate.metadata === "object" ? candidate.metadata : {};
      const intentId = String(candidate.id || ("intent-" + now + "-" + Math.round(Math.random() * 100000))).trim();
      return {
        id: intentId,
        queueKey: targetQueueKey,
        intentType: String(candidate.intentType || "save"),
        payload: payload,
        metadata: metadata,
        status: String(candidate.status || "pending"),
        createdAt: Number.isFinite(createdAt) ? createdAt : now,
        updatedAt: Number.isFinite(updatedAt) ? updatedAt : now,
      };
    }

    function openDatabase() {
      if (runtime.dbPromise !== undefined) {
        return runtime.dbPromise;
      }
      runtime.dbPromise = new Promise(function (resolve) {
        const indexedDBRef = parentWindow.indexedDB;
        if (!indexedDBRef || typeof indexedDBRef.open !== "function") {
          resolve(null);
          return;
        }
        let settled = false;
        function done(value) {
          if (settled) {
            return;
          }
          settled = true;
          resolve(value);
        }
        try {
          const request = indexedDBRef.open(DB_NAME, DB_VERSION);
          request.onupgradeneeded = function (event) {
            const db = event && event.target ? event.target.result : null;
            if (!db) {
              return;
            }
            let store = null;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
              store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
            } else if (event.target && event.target.transaction) {
              store = event.target.transaction.objectStore(STORE_NAME);
            }
            if (!store) {
              return;
            }
            if (!store.indexNames.contains("queueKey")) {
              store.createIndex("queueKey", "queueKey", { unique: false });
            }
            if (!store.indexNames.contains("updatedAt")) {
              store.createIndex("updatedAt", "updatedAt", { unique: false });
            }
          };
          request.onsuccess = function (event) {
            const db = event && event.target ? event.target.result : null;
            if (db && typeof db.addEventListener === "function") {
              db.addEventListener("versionchange", function () {
                try {
                  db.close();
                } catch (error) {
                  // ignore close failures
                }
                runtime.dbPromise = undefined;
              });
            }
            done(db);
          };
          request.onerror = function () {
            done(null);
          };
          request.onblocked = function () {
            done(null);
          };
        } catch (error) {
          done(null);
        }
      });
      return runtime.dbPromise;
    }

    function listIndexedDbQueue(db, targetQueueKey) {
      return new Promise(function (resolve) {
        try {
          const tx = db.transaction(STORE_NAME, "readonly");
          const store = tx.objectStore(STORE_NAME);
          const index = store.index("queueKey");
          const range =
            parentWindow.IDBKeyRange && typeof parentWindow.IDBKeyRange.only === "function"
              ? parentWindow.IDBKeyRange.only(targetQueueKey)
              : targetQueueKey;
          const request = index.openCursor(range);
          const rows = [];
          request.onsuccess = function (event) {
            const cursor = event && event.target ? event.target.result : null;
            if (!cursor) {
              resolve(normalizeQueueRows(rows, targetQueueKey));
              return;
            }
            if (cursor.value && cursor.value.queueKey === targetQueueKey) {
              rows.push(cursor.value);
            }
            cursor.continue();
          };
          request.onerror = function () {
            resolve(null);
          };
          tx.onabort = function () {
            resolve(null);
          };
          tx.onerror = function () {
            resolve(null);
          };
        } catch (error) {
          resolve(null);
        }
      });
    }

    function putIndexedDbIntent(db, record) {
      return new Promise(function (resolve) {
        try {
          const tx = db.transaction(STORE_NAME, "readwrite");
          const store = tx.objectStore(STORE_NAME);
          const request = store.put(record);
          request.onsuccess = function () {
            resolve(true);
          };
          request.onerror = function () {
            resolve(false);
          };
          tx.onabort = function () {
            resolve(false);
          };
          tx.onerror = function () {
            resolve(false);
          };
        } catch (error) {
          resolve(false);
        }
      });
    }

    function removeIndexedDbIntent(db, targetIntentId) {
      return new Promise(function (resolve) {
        try {
          const tx = db.transaction(STORE_NAME, "readwrite");
          const store = tx.objectStore(STORE_NAME);
          const request = store.delete(targetIntentId);
          request.onsuccess = function () {
            resolve(true);
          };
          request.onerror = function () {
            resolve(false);
          };
          tx.onabort = function () {
            resolve(false);
          };
          tx.onerror = function () {
            resolve(false);
          };
        } catch (error) {
          resolve(false);
        }
      });
    }

    function clearIndexedDbQueue(db, targetQueueKey) {
      return new Promise(function (resolve) {
        try {
          const tx = db.transaction(STORE_NAME, "readwrite");
          const store = tx.objectStore(STORE_NAME);
          const index = store.index("queueKey");
          const range =
            parentWindow.IDBKeyRange && typeof parentWindow.IDBKeyRange.only === "function"
              ? parentWindow.IDBKeyRange.only(targetQueueKey)
              : targetQueueKey;
          const request = index.openCursor(range);
          request.onsuccess = function (event) {
            const cursor = event && event.target ? event.target.result : null;
            if (!cursor) {
              resolve(true);
              return;
            }
            cursor.delete();
            cursor.continue();
          };
          request.onerror = function () {
            resolve(false);
          };
          tx.onabort = function () {
            resolve(false);
          };
          tx.onerror = function () {
            resolve(false);
          };
        } catch (error) {
          resolve(false);
        }
      });
    }

    async function listQueue(targetQueueKey) {
      const db = await openDatabase();
      if (db) {
        const indexedRows = await listIndexedDbQueue(db, targetQueueKey);
        if (Array.isArray(indexedRows)) {
          return {
            rows: indexedRows,
            pendingCount: indexedRows.length,
            backend: "indexeddb",
            status: indexedRows.length ? "pending" : "empty",
          };
        }
      }
      const localRows = readLocalQueue(targetQueueKey);
      return {
        rows: localRows,
        pendingCount: localRows.length,
        backend: getStorage() ? "localStorage" : "memory",
        status: localRows.length ? "pending" : "empty",
      };
    }

    async function enqueueIntent(targetQueueKey, rawIntent) {
      const record = normalizeIntent(targetQueueKey, rawIntent);
      const db = await openDatabase();
      if (db) {
        const stored = await putIndexedDbIntent(db, record);
        if (stored) {
          return {
            backend: "indexeddb",
            intent: record,
          };
        }
      }
      const localRows = readLocalQueue(targetQueueKey).filter(function (row) {
        return row.id !== record.id;
      });
      localRows.push(record);
      writeLocalQueue(targetQueueKey, localRows);
      return {
        backend: getStorage() ? "localStorage" : "memory",
        intent: record,
      };
    }

    async function removeIntent(targetQueueKey, targetIntentId) {
      const normalizedIntentId = String(targetIntentId || "").trim();
      if (!normalizedIntentId) {
        return await listQueue(targetQueueKey);
      }
      const db = await openDatabase();
      if (db) {
        await removeIndexedDbIntent(db, normalizedIntentId);
      }
      const localRows = readLocalQueue(targetQueueKey).filter(function (row) {
        return row.id !== normalizedIntentId;
      });
      writeLocalQueue(targetQueueKey, localRows);
      return await listQueue(targetQueueKey);
    }

    async function clearQueue(targetQueueKey) {
      const db = await openDatabase();
      if (db) {
        await clearIndexedDbQueue(db, targetQueueKey);
      }
      writeLocalQueue(targetQueueKey, []);
      return await listQueue(targetQueueKey);
    }

    function dispatchCustomEvent(eventName, detail) {
      const normalizedName = String(eventName || "").trim();
      if (!normalizedName || !parentWindow.dispatchEvent) {
        return;
      }
      try {
        if (typeof parentWindow.CustomEvent === "function") {
          parentWindow.dispatchEvent(new parentWindow.CustomEvent(normalizedName, { detail: detail }));
          return;
        }
      } catch (error) {
        // ignore event dispatch fallback failures
      }
      try {
        if (doc && typeof doc.createEvent === "function") {
          const fallbackEvent = doc.createEvent("CustomEvent");
          fallbackEvent.initCustomEvent(normalizedName, false, false, detail);
          parentWindow.dispatchEvent(fallbackEvent);
        }
      } catch (error) {
        // ignore event dispatch failures
      }
    }

    function ensureStyle() {
      if (doc.getElementById(NOTICE_STYLE_ID) || !doc.head) {
        return;
      }
      const style = doc.createElement("style");
      style.id = NOTICE_STYLE_ID;
      style.textContent = `
.sl-offline-intent-queue {
  margin: 0.45rem 0 0.7rem;
  padding: 0.5rem 0.66rem;
  border-radius: 10px;
  border: 1px solid #d7dde7;
  background: rgba(255, 255, 255, 0.95);
  color: #1f2937;
  font-size: 0.8rem;
  line-height: 1.4;
  display: none;
  gap: 0.56rem;
  align-items: center;
  justify-content: space-between;
}
.sl-offline-intent-queue[data-visible="1"] {
  display: flex;
}
.sl-offline-intent-queue[data-status="pending"] {
  border-color: #fde68a;
  background: rgba(255, 251, 235, 0.95);
  color: #92400e;
}
.sl-offline-intent-queue[data-status="replay"] {
  border-color: #bfdbfe;
  background: rgba(239, 246, 255, 0.95);
  color: #1e3a8a;
}
.sl-offline-intent-queue[data-status="replayed"] {
  border-color: #86efac;
  background: rgba(236, 253, 243, 0.95);
  color: #166534;
}
.sl-offline-intent-queue__text {
  flex: 1 1 auto;
}
.sl-offline-intent-queue__button {
  border: 1px solid #c4ccd8;
  border-radius: 999px;
  background: #ffffff;
  color: #1f2937;
  padding: 0.2rem 0.72rem;
  font-size: 0.76rem;
  line-height: 1.2;
  cursor: pointer;
}
.sl-offline-intent-queue__button:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}
@media (max-width: 820px) {
  .sl-offline-intent-queue {
    flex-direction: column;
    align-items: stretch;
  }
  .sl-offline-intent-queue__button {
    width: 100%;
    min-height: 32px;
  }
}
      `;
      doc.head.appendChild(style);
    }

    function backendLabel(backendName) {
      if (backendName === "indexeddb") {
        return "IndexedDB";
      }
      if (backendName === "localStorage") {
        return "localStorage";
      }
      return "memory";
    }

    function resolveNoticeHost() {
      return doc.querySelector('[data-testid="stMainBlockContainer"]') || doc.body;
    }

    function ensureNotice(instance) {
      ensureStyle();
      const safeQueueKey = instance.queueKey.replace(/[^A-Za-z0-9_-]/g, "-");
      const noticeId = "sl-offline-intent-queue-notice-" + safeQueueKey;
      let root = doc.getElementById(noticeId);
      if (!root) {
        root = doc.createElement("div");
        root.id = noticeId;
        root.className = "sl-offline-intent-queue";
        root.setAttribute("data-visible", "0");
        root.setAttribute("data-status", "idle");
        const textNode = doc.createElement("div");
        textNode.className = "sl-offline-intent-queue__text";
        textNode.setAttribute("data-role", "text");
        const button = doc.createElement("button");
        button.type = "button";
        button.className = "sl-offline-intent-queue__button";
        button.setAttribute("data-role", "replay");
        button.textContent = "再試行を要求";
        root.appendChild(textNode);
        root.appendChild(button);
        const host = resolveNoticeHost();
        if (host && host.firstChild) {
          host.insertBefore(root, host.firstChild);
        } else if (host) {
          host.appendChild(root);
        }
      }
      instance.noticeElement = root;
      instance.textElement = root.querySelector('[data-role="text"]');
      instance.replayButton = root.querySelector('[data-role="replay"]');
      if (instance.replayButton && !instance.replayButtonBound) {
        instance.replayButton.addEventListener("click", function () {
          requestReplay(instance, "manual-button");
        });
        instance.replayButtonBound = true;
      }
      return root;
    }

    function setFlash(instance, message, status, durationMs) {
      if (!message) {
        return;
      }
      const duration = Number(durationMs);
      const resolvedDuration = Number.isFinite(duration) ? Math.max(900, duration) : 2600;
      instance.flashMessage = String(message);
      instance.flashStatus = String(status || "idle");
      instance.flashUntil = Date.now() + resolvedDuration;
    }

    function renderNotice(instance) {
      const root = ensureNotice(instance);
      if (!root) {
        return;
      }
      const now = Date.now();
      const textNode = instance.textElement;
      const replayButton = instance.replayButton;
      let visible = false;
      let status = "idle";
      let text = "";

      if (instance.flashUntil && instance.flashUntil > now && instance.flashMessage) {
        visible = true;
        status = instance.flashStatus || "idle";
        text = instance.flashMessage;
      } else if (instance.pendingCount > 0) {
        visible = true;
        status = "pending";
        text =
          String(instance.options.queueLabel || "保存キュー") +
          ": 未処理 " +
          String(instance.pendingCount) +
          "件（" +
          backendLabel(instance.backend) +
          "）";
        if (instance.options.autoReplayOnOnline) {
          text += " / オンライン復帰時に再試行フックを実行";
        }
      } else if (instance.options.showWhenEmpty) {
        visible = true;
        status = "idle";
        text = String(instance.options.queueLabel || "保存キュー") + ": 未処理の保存はありません";
      } else {
        instance.flashUntil = 0;
        instance.flashMessage = "";
        instance.flashStatus = "idle";
      }

      root.setAttribute("data-visible", visible ? "1" : "0");
      root.setAttribute("data-status", status);
      if (textNode) {
        textNode.textContent = text;
      }
      if (replayButton) {
        replayButton.textContent = String(instance.options.replayButtonLabel || "再試行を要求");
        replayButton.style.display = instance.options.showReplayButton ? "" : "none";
        replayButton.disabled = instance.pendingCount <= 0;
        replayButton.setAttribute("aria-hidden", instance.options.showReplayButton ? "false" : "true");
      }
    }

    async function refreshInstance(instance, source) {
      const summary = await listQueue(instance.queueKey);
      instance.pendingCount = summary.pendingCount;
      instance.backend = summary.backend;
      instance.status = summary.status;
      instance.lastRefreshSource = String(source || "");
      renderNotice(instance);
      return summary;
    }

    async function requestReplay(instance, reason) {
      const summary = await refreshInstance(instance, reason || "manual");
      if (summary.pendingCount <= 0) {
        return false;
      }
      dispatchCustomEvent(instance.options.replayEventName, {
        queueKey: instance.queueKey,
        pendingCount: summary.pendingCount,
        backend: summary.backend,
        status: summary.status,
        reason: String(reason || "manual"),
        requestedAt: Date.now(),
      });
      setFlash(
        instance,
        instance.options.replayRequestedMessage || "保存再試行フックを呼び出しました。",
        "replay",
        3600
      );
      renderNotice(instance);
      return true;
    }

    function ensureBridge(targetQueueKey, options) {
      const instance = runtime.instances[targetQueueKey] || {};
      runtime.instances[targetQueueKey] = instance;
      instance.queueKey = targetQueueKey;
      instance.options = Object.assign(
        {
          queueLabel: "保存キュー",
          replayEventName: DEFAULT_REPLAY_EVENT_NAME,
          replayAckEventName: DEFAULT_REPLAY_EVENT_NAME + ":ack",
          replayButtonLabel: "再試行を要求",
          replayRequestedMessage: "保存再試行フックを呼び出しました。",
          autoReplayOnOnline: true,
          showReplayButton: false,
          showWhenEmpty: false,
        },
        instance.options || {},
        options || {}
      );
      ensureNotice(instance);

      if (!instance.bound && parentWindow.addEventListener) {
        instance.bound = true;
        instance.onlineHandler = function () {
          if (!instance.options.autoReplayOnOnline) {
            return;
          }
          if (instance.onlineReplayTimer) {
            parentWindow.clearTimeout(instance.onlineReplayTimer);
          }
          instance.onlineReplayTimer = parentWindow.setTimeout(function () {
            requestReplay(instance, "online-recovered");
          }, 180);
        };
        parentWindow.addEventListener("online", instance.onlineHandler);
      }

      const ackEventName = String(instance.options.replayAckEventName || "").trim();
      if (ackEventName && parentWindow.addEventListener && ackEventName !== instance.boundAckEventName) {
        if (instance.boundAckEventName && instance.replayAckHandler) {
          parentWindow.removeEventListener(instance.boundAckEventName, instance.replayAckHandler);
        }
        instance.replayAckHandler = function (event) {
          const detail = event && event.detail ? event.detail : {};
          const detailQueueKey = String(detail.queueKey || "").trim();
          if (detailQueueKey && detailQueueKey !== instance.queueKey) {
            return;
          }
          queueRuntimeOperation(instance.queueKey, async function () {
            const processedIds = Array.isArray(detail.processedIds)
              ? detail.processedIds
                  .map(function (value) {
                    return String(value || "").trim();
                  })
                  .filter(function (value) {
                    return !!value;
                  })
              : [];
            if (detail.clearAll) {
              await clearQueue(instance.queueKey);
            } else if (processedIds.length) {
              for (let index = 0; index < processedIds.length; index += 1) {
                await removeIntent(instance.queueKey, processedIds[index]);
              }
            }
            await refreshInstance(instance, "replay-ack");
            const requestedCount = Number(detail.replayedCount);
            const resolvedCount =
              Number.isFinite(requestedCount) && requestedCount > 0 ? requestedCount : processedIds.length;
            const defaultMessage =
              resolvedCount > 0
                ? "再試行完了: " + String(resolvedCount) + "件をキューから外しました。"
                : "再試行完了を確認しました。";
            setFlash(instance, String(detail.message || defaultMessage), "replayed", 4200);
            renderNotice(instance);
          });
        };
        parentWindow.addEventListener(ackEventName, instance.replayAckHandler);
        instance.boundAckEventName = ackEventName;
      }
      return instance;
    }

    const api = runtime.api || {};
    runtime.api = api;
    parentWindow.__ichigodbOfflineIntentQueueAPI = api;
    api.enqueueIntent = enqueueIntent;
    api.listPendingStatus = async function (targetQueueKey) {
      const normalizedQueueKey = String(targetQueueKey || "").trim();
      if (!normalizedQueueKey) {
        return { pendingCount: 0, backend: "memory", status: "empty" };
      }
      const summary = await listQueue(normalizedQueueKey);
      return {
        pendingCount: summary.pendingCount,
        backend: summary.backend,
        status: summary.status,
      };
    };
    api.removeIntent = removeIntent;
    api.clearQueue = clearQueue;

    const replayEventName = String(config.replayEventName || DEFAULT_REPLAY_EVENT_NAME).trim() || DEFAULT_REPLAY_EVENT_NAME;
    const replayAckEventName =
      String(config.replayAckEventName || (replayEventName + ":ack")).trim() || (replayEventName + ":ack");
    const queueLabel = String(config.queueLabel || "保存キュー").trim() || "保存キュー";
    const mode = String(config.mode || "bridge").toLowerCase();
    const bridgeOptions = {
      queueLabel: queueLabel,
      replayEventName: replayEventName,
      replayAckEventName: replayAckEventName,
      replayButtonLabel: String(config.replayButtonLabel || "再試行を要求"),
      replayRequestedMessage: String(config.replayRequestedMessage || "保存再試行フックを呼び出しました。"),
      autoReplayOnOnline: config.autoReplayOnOnline !== false,
      showReplayButton: config.showReplayButton === true,
      showWhenEmpty: config.showWhenEmpty === true,
    };

    return await queueRuntimeOperation(queueKey, async function () {
      if (mode === "bridge") {
        const instance = ensureBridge(queueKey, bridgeOptions);
        await refreshInstance(instance, "bridge");
        return;
      }

      if (mode === "enqueue") {
        await enqueueIntent(queueKey, config.intent);
        const instance = runtime.instances[queueKey];
        if (instance) {
          await refreshInstance(instance, "enqueue");
        }
        return;
      }

      if (mode === "remove") {
        await removeIntent(queueKey, config.intentId);
        const instance = runtime.instances[queueKey];
        if (instance) {
          await refreshInstance(instance, "remove");
          if (config.notifyMessage) {
            setFlash(instance, String(config.notifyMessage), "replayed", 3600);
            renderNotice(instance);
          }
        }
        return;
      }

      if (mode === "clear") {
        await clearQueue(queueKey);
        const instance = runtime.instances[queueKey];
        if (instance) {
          await refreshInstance(instance, "clear");
          if (config.notifyMessage) {
            setFlash(instance, String(config.notifyMessage), "replayed", 3600);
            renderNotice(instance);
          }
        }
        return;
      }

      if (mode === "status") {
        const instance = ensureBridge(queueKey, bridgeOptions);
        await refreshInstance(instance, "status");
        return;
      }

      if (mode === "request_replay") {
        const instance = ensureBridge(queueKey, bridgeOptions);
        await requestReplay(instance, String(config.reason || "manual"));
        return;
      }

      if (mode === "notify_replayed") {
        const processedIds = Array.isArray(config.processedIds)
          ? config.processedIds
              .map(function (value) {
                return String(value || "").trim();
              })
              .filter(function (value) {
                return !!value;
              })
          : [];
        dispatchCustomEvent(replayAckEventName, {
          queueKey: queueKey,
          processedIds: processedIds,
          clearAll: !!config.clearAll,
          replayedCount: Number(config.replayedCount || 0),
          message: config.message ? String(config.message) : "",
        });
      }
    });
  } catch (error) {
    // keep bridge resilient even if browser APIs fail
  }
})();
</script>
""".replace("__CONFIG__", config_json)


def _inject(config: Mapping[str, object]) -> None:
    config_json = json.dumps(dict(config), ensure_ascii=False).replace("</", "<\\/")
    components.html(_build_script(config_json), height=0)


def render_offline_intent_queue_bridge(
    queue_key: str,
    *,
    queue_label: str = "保存キュー",
    replay_event_name: str = _DEFAULT_REPLAY_EVENT_NAME,
    replay_ack_event_name: str | None = None,
    replay_button_label: str = "再試行を要求",
    replay_requested_message: str = "保存再試行フックを呼び出しました。",
    auto_replay_on_online: bool = True,
    show_replay_button: bool = False,
    show_when_empty: bool = False,
) -> None:
    """Render a queue status bridge and online replay hook dispatcher."""
    normalized_queue_key = _normalize_queue_key(queue_key)
    normalized_replay_event = _normalize_event_name(replay_event_name, fallback=_DEFAULT_REPLAY_EVENT_NAME)
    normalized_ack_event = _normalize_event_name(
        replay_ack_event_name,
        fallback=f"{normalized_replay_event}:ack",
    )
    _inject(
        {
            "mode": "bridge",
            "queueKey": normalized_queue_key,
            "queueLabel": str(queue_label or "保存キュー"),
            "replayEventName": normalized_replay_event,
            "replayAckEventName": normalized_ack_event,
            "replayButtonLabel": str(replay_button_label or "再試行を要求"),
            "replayRequestedMessage": str(replay_requested_message or "保存再試行フックを呼び出しました。"),
            "autoReplayOnOnline": bool(auto_replay_on_online),
            "showReplayButton": bool(show_replay_button),
            "showWhenEmpty": bool(show_when_empty),
        }
    )


def enqueue_offline_intent(
    queue_key: str,
    *,
    intent_id: str | None = None,
    intent_type: str = "save",
    payload: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    status: str = "pending",
) -> str:
    """Enqueue a save intent in browser storage and return its normalized intent ID."""
    resolved_intent_id = _normalize_intent_id(intent_id, fallback=str(uuid4()))
    _inject(
        {
            "mode": "enqueue",
            "queueKey": _normalize_queue_key(queue_key),
            "intent": {
                "id": resolved_intent_id,
                "intentType": str(intent_type or "save")[:_MAX_INTENT_TYPE_LENGTH],
                "payload": _safe_mapping(payload),
                "metadata": _safe_mapping(metadata),
                "status": str(status or "pending"),
            },
        }
    )
    return resolved_intent_id


def refresh_offline_intent_queue_status(
    queue_key: str,
    *,
    queue_label: str = "保存キュー",
    replay_event_name: str = _DEFAULT_REPLAY_EVENT_NAME,
    replay_ack_event_name: str | None = None,
) -> None:
    """Refresh pending queue count/status without mutating entries."""
    normalized_replay_event = _normalize_event_name(replay_event_name, fallback=_DEFAULT_REPLAY_EVENT_NAME)
    normalized_ack_event = _normalize_event_name(
        replay_ack_event_name,
        fallback=f"{normalized_replay_event}:ack",
    )
    _inject(
        {
            "mode": "status",
            "queueKey": _normalize_queue_key(queue_key),
            "queueLabel": str(queue_label or "保存キュー"),
            "replayEventName": normalized_replay_event,
            "replayAckEventName": normalized_ack_event,
        }
    )


def remove_offline_intent(queue_key: str, intent_id: str, *, notify_message: str | None = None) -> None:
    """Remove one processed intent from the queue."""
    normalized_intent_id = _normalize_intent_id(intent_id)
    _inject(
        {
            "mode": "remove",
            "queueKey": _normalize_queue_key(queue_key),
            "intentId": normalized_intent_id,
            "notifyMessage": str(notify_message or ""),
        }
    )


def clear_offline_intent_queue(queue_key: str, *, notify_message: str | None = None) -> None:
    """Clear all pending intents for the queue key."""
    _inject(
        {
            "mode": "clear",
            "queueKey": _normalize_queue_key(queue_key),
            "notifyMessage": str(notify_message or ""),
        }
    )


def trigger_offline_intent_replay(
    queue_key: str,
    *,
    reason: str = "manual",
    replay_event_name: str = _DEFAULT_REPLAY_EVENT_NAME,
    replay_ack_event_name: str | None = None,
    queue_label: str = "保存キュー",
) -> None:
    """Trigger replay hook dispatch for the queue."""
    normalized_replay_event = _normalize_event_name(replay_event_name, fallback=_DEFAULT_REPLAY_EVENT_NAME)
    normalized_ack_event = _normalize_event_name(
        replay_ack_event_name,
        fallback=f"{normalized_replay_event}:ack",
    )
    _inject(
        {
            "mode": "request_replay",
            "queueKey": _normalize_queue_key(queue_key),
            "queueLabel": str(queue_label or "保存キュー"),
            "replayEventName": normalized_replay_event,
            "replayAckEventName": normalized_ack_event,
            "reason": str(reason or "manual"),
        }
    )


def notify_offline_intent_replayed(
    queue_key: str,
    *,
    processed_ids: Sequence[str] | None = None,
    replayed_count: int | None = None,
    clear_all: bool = False,
    message: str | None = None,
    replay_event_name: str = _DEFAULT_REPLAY_EVENT_NAME,
    replay_ack_event_name: str | None = None,
) -> None:
    """Notify the bridge that replay completed so it can clear and announce."""
    normalized_replay_event = _normalize_event_name(replay_event_name, fallback=_DEFAULT_REPLAY_EVENT_NAME)
    normalized_ack_event = _normalize_event_name(
        replay_ack_event_name,
        fallback=f"{normalized_replay_event}:ack",
    )
    normalized_ids = [
        _normalize_intent_id(value)
        for value in (processed_ids or [])
        if str(value or "").strip()
    ]
    _inject(
        {
            "mode": "notify_replayed",
            "queueKey": _normalize_queue_key(queue_key),
            "replayEventName": normalized_replay_event,
            "replayAckEventName": normalized_ack_event,
            "processedIds": normalized_ids,
            "replayedCount": int(replayed_count or 0),
            "clearAll": bool(clear_all),
            "message": str(message or ""),
        }
    )
