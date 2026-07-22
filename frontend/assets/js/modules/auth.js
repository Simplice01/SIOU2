/**
 * auth.js
 * Service d'authentification de SIOU (couche métier).
 *
 * S'appuie sur `api.js` pour le réseau et sur `storage.js` pour la
 * persistance. Expose une API stable au reste de l'application :
 *   login / logout / getCurrentUser / fetchCurrentUser
 *   isAuthenticated / getUser / getRole / hasRole
 *
 * Contrat serveur (voir backend/routers/auth.py) :
 *   POST /auth/login   { username, password }
 *      → { access_token, refresh_token, token_type, user }
 *   POST /auth/refresh { refresh_token } → { access_token, token_type }
 *   POST /auth/logout  → { detail }
 *   GET  /auth/me      → utilisateur courant
 *   PATCH /auth/me     { first_name?, last_name? } → utilisateur mis à jour
 */

import {
  apiFetch,
  persistSession,
  setStoredUser,
  getStoredUser,
  clearSession,
  getAccessToken,
} from './api.js';

/**
 * Authentifie l'utilisateur et persiste jetons + profil.
 * @param {string}  username
 * @param {string}  password
 * @param {boolean} [remember] mémoriser la session (localStorage) ou non
 *                             (sessionStorage, effacée à la fermeture)
 * @returns {Promise<Object>} l'utilisateur connecté
 * @throws {ApiError}
 */
export async function login(username, password, remember = false) {
  const data = await apiFetch('/auth/login', {
    method: 'POST',
    auth: false,
    body: { username, password },
  });

  persistSession({
    access: data.access_token,
    refresh: data.refresh_token,
    user: data.user,
    remember,
  });
  return data.user;
}

/**
 * Déconnecte l'utilisateur. Notifie le serveur au mieux (endpoint stateless),
 * puis nettoie systématiquement la session locale.
 * @returns {Promise<void>}
 */
export async function logout() {
  try {
    if (getAccessToken()) await apiFetch('/auth/logout', { method: 'POST' });
  } catch {
    // La déconnexion locale prime : on ignore toute erreur réseau ici.
  } finally {
    clearSession();
  }
}

/** @returns {boolean} true si un jeton d'accès est présent. */
export function isAuthenticated() {
  return Boolean(getAccessToken());
}

/** @returns {Object|null} l'utilisateur mis en cache localement. */
export function getUser() {
  return getStoredUser();
}

/** @returns {string|null} le rôle de l'utilisateur mis en cache. */
export function getRole() {
  return getUser()?.role ?? null;
}

/**
 * Indique si l'utilisateur possède l'un des rôles attendus.
 * Base de l'autorisation RBAC côté client, à étendre au besoin.
 * @param {...string} roles
 * @returns {boolean}
 */
export function hasRole(...roles) {
  const role = getRole();
  return role !== null && roles.includes(role);
}

/**
 * Récupère le profil à jour depuis le serveur et rafraîchit le cache local.
 * @returns {Promise<Object>}
 */
export async function fetchCurrentUser() {
  const user = await apiFetch('/auth/me');
  setStoredUser(user);
  return user;
}

/**
 * Met à jour le profil de l'utilisateur courant (self-service) et
 * rafraîchit le cache local pour que la topbar reflète les changements.
 * Seuls prénom et nom sont modifiables par l'utilisateur lui-même.
 * @param {{ first_name?: string, last_name?: string }} patch
 * @returns {Promise<Object>} l'utilisateur mis à jour
 * @throws {ApiError}
 */
export async function updateCurrentUser(patch) {
  const user = await apiFetch('/auth/me', { method: 'PATCH', body: patch });
  setStoredUser(user);
  return user;
}
