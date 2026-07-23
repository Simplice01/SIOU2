/**
 * feedback-service.js
 * Signalement des réponses de l'assistant. Enveloppe mince au-dessus de
 * `api.js`. Récupère l'utilisateur courant via `auth.js` pour renseigner
 * `user_id`.
 *
 * Contrat serveur :
 *   POST   /api/feedbacks                { conversation_id?, message_id?, user_id?, rating(1-5), comment? }
 *   GET    /api/admin/feedbacks           → liste (modération, réservé admin)
 *   DELETE /api/admin/feedbacks/{id}      → { detail } (réservé admin)
 * Note : l'endpoint utilisateur est au pluriel (« feedbacks »).
 */

import { apiFetch } from './api.js';
import { getUser, hasRole } from './auth.js';

/**
 * Signale une réponse jugée incorrecte (note basse = signalement).
 * @param {Object} params
 * @param {string} [params.conversationId]
 * @param {string} [params.messageId]
 * @param {string} [params.comment]
 * @param {number} [params.rating] 1 (mauvaise) à 5 (excellente) — défaut 1
 * @returns {Promise<Object>} le feedback créé
 * @throws {ApiError}
 */
export function reportAnswer({ conversationId = null, messageId = null, comment = null, rating = 1 } = {}) {
  const user = getUser();
  return apiFetch('/feedbacks', {
    method: 'POST',
    body: {
      conversation_id: conversationId,
      message_id: messageId,
      user_id: user?.id ?? null,
      rating,
      comment,
    },
  });
}

/* ------------------------------------------------------------------ */
/*  Administration (réservé admin)                                     */
/* ------------------------------------------------------------------ */

/** Liste tous les signalements pour modération. @returns {Promise<Array>} */
export function listFeedbacks() {
  if (hasRole('admin', 'ministry_manager', 'validator')) {
    return apiFetch('/admin/feedbacks');
  }
  return apiFetch('/feedbacks');
}

/** Supprime un signalement. @returns {Promise<Object>} */
export function deleteFeedback(id) {
  if (hasRole('admin', 'ministry_manager')) {
    return apiFetch(`/admin/feedbacks/${id}`, { method: 'DELETE' });
  }
  return apiFetch(`/feedbacks/${id}`, { method: 'DELETE' });
}
