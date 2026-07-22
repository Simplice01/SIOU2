/**
 * stats-service.js
 * Accès aux statistiques agrégées du tableau de bord. Enveloppe mince
 * au-dessus de `api.js` (jeton JWT ajouté automatiquement).
 *
 * Contrat serveur (backend/routers/stats.py) :
 *   GET /api/stats → {
 *     conversations: { current_month, previous_month, change_percent },
 *     documents:     { total, recent, by_status: [{ status, label, count, percentage }] }
 *   }
 */

import { apiFetch } from './api.js';

/** Récupère les statistiques du tableau de bord. @returns {Promise<Object>} */
export function getStatistics() {
  return apiFetch('/stats');
}
