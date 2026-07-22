/**
 * conversation-service.js
 * Accès à l'API des conversations. Enveloppe mince au-dessus de `api.js`.
 *
 * Contrat serveur (backend/routers/conversation.py) :
 *   GET    /api/conversations            → [{ id, user_id, title, created_at, updated_at }]
 *   GET    /api/conversations/{id}/messages → [{ id, sender_type, content, model_used, created_at }]
 *   PATCH  /api/conversations/{id}        { title } → conversation mise à jour
 *   DELETE /api/conversations/{id}        → { detail }
 *
 * L'appartenance est vérifiée côté serveur (une conversation d'un autre
 * utilisateur renvoie 404).
 */

import { apiFetch } from './api.js';

/**
 * Liste les conversations de l'utilisateur connecté.
 * @returns {Promise<Array>} conversations (peut être vide)
 * @throws {ApiError}
 */
export function listConversations() {
  return apiFetch('/conversations');
}

/**
 * Récupère les messages d'une conversation (ordre chronologique), pour rejouer le fil.
 * @param {string} id identifiant de la conversation
 * @returns {Promise<Array>} messages [{ id, sender_type, content, model_used, created_at }]
 * @throws {ApiError}
 */
export function getConversationMessages(id) {
  return apiFetch(`/conversations/${id}/messages`);
}

/**
 * Renomme une conversation.
 * @param {string} id     identifiant de la conversation
 * @param {string} title  nouveau titre
 * @returns {Promise<Object>} la conversation mise à jour
 * @throws {ApiError}
 */
export function updateConversation(id, { title }) {
  return apiFetch(`/conversations/${id}`, { method: 'PATCH', body: { title } });
}

/**
 * Supprime une conversation.
 * @param {string} id identifiant de la conversation
 * @returns {Promise<Object>} { detail }
 * @throws {ApiError}
 */
export function deleteConversation(id) {
  return apiFetch(`/conversations/${id}`, { method: 'DELETE' });
}
