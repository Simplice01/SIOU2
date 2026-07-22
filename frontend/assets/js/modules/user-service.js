/**
 * user-service.js
 * Accès à l'API d'administration des comptes. Enveloppe mince au-dessus de
 * `api.js`. Toutes ces routes sont réservées au rôle `admin` côté serveur.
 *
 * Contrat serveur (backend/routers/admin.py) :
 *   GET    /api/admin/users        → [{ id, username, first_name, last_name, role, is_active, created_at }]
 *   POST   /api/admin/users        { username, password, first_name?, last_name?, role?, is_active? } → user
 *   GET    /api/admin/users/{id}   → user
 *   PATCH  /api/admin/users/{id}   { first_name?, last_name?, role?, is_active? } → user
 *   DELETE /api/admin/users/{id}   → { detail }
 */

import { apiFetch } from './api.js';

/** Liste tous les comptes. @returns {Promise<Array>} */
export function listUsers() {
  return apiFetch('/admin/users');
}

/** Crée un compte (mot de passe requis, min. 8 caractères). @returns {Promise<Object>} */
export function createUser(payload) {
  return apiFetch('/admin/users', { method: 'POST', body: payload });
}

/** Met à jour un compte (identité, rôle, activation). @returns {Promise<Object>} */
export function updateUser(id, patch) {
  return apiFetch(`/admin/users/${id}`, { method: 'PATCH', body: patch });
}

/** Supprime un compte. @returns {Promise<Object>} */
export function deleteUser(id) {
  return apiFetch(`/admin/users/${id}`, { method: 'DELETE' });
}
