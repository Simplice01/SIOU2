/**
 * chat-service.js
 * Accès à l'API de conversation (RAG). Enveloppe mince au-dessus de `api.js` :
 * ce module ne connaît que le contrat de l'endpoint, pas l'UI.
 *
 * Contrat serveur (backend/routers/chat.py) :
 *   POST /api/chat        { question, conversation_id?, document_ids? }
 *     → { text, sources:[{title, meta, document_id?, score?}], confidence,
 *         model, conversation_id }               (réponse complète, non streamée)
 *
 *   POST /api/chat/stream { question, conversation_id?, document_ids? }
 *     → flux Server-Sent Events :
 *         event: meta   data: { conversation_id }
 *         event: token  data: { delta }
 *         event: done   data: { sources, confidence, model }
 *         event: error  data: { detail }
 */

import { API_BASE, ApiError, apiFetch, getAccessToken } from './api.js';

// La génération LLM peut durer plusieurs secondes : on accorde un délai large à
// la variante non streamée (bien au-delà des 15 s par défaut d'`api.js`).
const RAG_TIMEOUT_MS = 300000; // 5 min

/**
 * Envoie une question à l'assistant SIOU (réponse complète en une fois).
 * @param {Object}   params
 * @param {string}   params.question
 * @param {string}   [params.conversationId] pour rattacher la question à un fil
 * @param {string[]} [params.documentIds]    restreindre à certains documents
 * @returns {Promise<Object>} la réponse structurée du backend
 * @throws {ApiError}
 */
export function askQuestion({ question, conversationId = null, documentIds = [] }) {
  const body = { question };
  if (conversationId) body.conversation_id = conversationId;
  if (Array.isArray(documentIds) && documentIds.length) body.document_ids = documentIds;

  return apiFetch('/chat', { method: 'POST', body, timeout: RAG_TIMEOUT_MS });
}

/**
 * Envoie une question en **streaming** (SSE) et notifie l'appelant au fil de l'eau.
 *
 * `fetch` + `ReadableStream` (et non `EventSource`, qui ne permet pas d'envoyer
 * l'en-tête `Authorization`). Les callbacks sont invoqués dans l'ordre du flux.
 *
 * @param {Object}   params
 * @param {string}   params.question
 * @param {string}   [params.conversationId]
 * @param {string[]} [params.documentIds]
 * @param {(meta:{conversation_id:string}) => void}                 [params.onMeta]
 * @param {(delta:string) => void}                                  [params.onToken]
 * @param {(done:{sources:Array, confidence:number, model:string}) => void} [params.onDone]
 * @param {AbortSignal} [params.signal] pour annuler le flux
 * @returns {Promise<void>} résolue à la fin du flux
 * @throws {ApiError} en cas d'échec réseau/HTTP ou d'évènement `error`
 */
export async function streamQuestion({
  question,
  conversationId = null,
  documentIds = [],
  onMeta,
  onToken,
  onDone,
  signal,
} = {}) {
  const body = { question };
  if (conversationId) body.conversation_id = conversationId;
  if (Array.isArray(documentIds) && documentIds.length) body.document_ids = documentIds;

  const headers = { 'Content-Type': 'application/json' };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw new ApiError('Requête annulée.', { type: 'timeout' });
    throw new ApiError('Impossible de joindre le serveur. Vérifiez votre connexion.', {
      type: 'network',
    });
  }

  if (!response.ok || !response.body) {
    let detail = 'Le service est momentanément indisponible.';
    try {
      const data = await response.json();
      if (data?.detail) detail = data.detail;
    } catch {
      /* corps non-JSON : on garde le message par défaut */
    }
    throw new ApiError(detail, { type: 'http', status: response.status });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // Le protocole SSE sépare les évènements par une ligne vide (\n\n).
  const dispatch = (rawEvent) => {
    let event = 'message';
    let data = '';
    for (const line of rawEvent.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trim();
    }
    if (!data) return;
    const payload = JSON.parse(data);
    if (event === 'meta') onMeta?.(payload);
    else if (event === 'token') onToken?.(payload.delta || '');
    else if (event === 'done') onDone?.(payload);
    else if (event === 'error') {
      throw new ApiError(payload.detail || 'Erreur de génération.', { type: 'http', status: 503 });
    }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex;
    while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      if (rawEvent.trim()) dispatch(rawEvent);
    }
  }
  // Évènement résiduel éventuel (flux clos sans \n\n final).
  if (buffer.trim()) dispatch(buffer);
}
