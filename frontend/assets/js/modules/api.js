/**
 * api.js
 * Point d'entrée réseau unique de SIOU (couche bas niveau).
 *
 * Responsabilités :
 *   - construire les requêtes vers l'API FastAPI (base URL configurable) ;
 *   - attacher automatiquement le jeton d'accès (`Authorization: Bearer …`) ;
 *   - appliquer un délai d'expiration (timeout) via AbortController ;
 *   - normaliser toutes les erreurs (réseau, timeout, HTTP) en `ApiError` ;
 *   - rafraîchir le jeton d'accès sur un 401 (une seule tentative, mutualisée),
 *     rejouer la requête, et nettoyer la session si le refresh échoue.
 *
 * Ce module ne connaît PAS la logique métier d'authentification (formulaire,
 * profil utilisateur) : c'est le rôle de `auth.js`, qui s'appuie sur lui.
 * Il détient en revanche les accesseurs de jetons afin d'éviter toute
 * dépendance circulaire avec `auth.js`.
 */

import { storage, session, KEYS } from './storage.js';

/**
 * Base de l'API. Par défaut `/api` (même origine, cas de production).
 * Surchargeable en développement (frontend et backend sur des ports
 * différents) via, au choix :
 *   window.SIOU_API_BASE = 'http://localhost:8000/api'
 *   <html data-api-base="http://localhost:8000/api">
 */
export const API_BASE = (
  window.SIOU_API_BASE ||
  document.documentElement.dataset.apiBase ||
  (window.location.hostname.endsWith('vercel.app') ? 'https://siou2.onrender.com/api' : '') ||
  '/api'
).replace(/\/+$/, '');

const DEFAULT_TIMEOUT = 15000;
const LOGIN_PAGE = '/login.html';

/** Erreur réseau/API normalisée, exploitable par la couche UI. */
export class ApiError extends Error {
  /**
   * @param {string} message  message affichable à l'utilisateur
   * @param {Object} [options]
   * @param {'network'|'timeout'|'http'|'auth'} [options.type]
   * @param {number} [options.status] code HTTP éventuel
   * @param {*} [options.data] corps de réponse éventuel
   */
  constructor(message, { type = 'http', status = 0, data = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.type = type;
    this.status = status;
    this.data = data;
  }
}

/**
 * Traduit une erreur (ApiError ou autre) en message affichable, cohérent
 * dans toute l'application. Centralisé ici pour éviter la duplication du
 * mapping entre les différents contrôleurs (login, chat, documents…).
 * @param {*} error
 * @param {string} [fallback]
 * @returns {string}
 */
export function messageFromError(error, fallback = 'Une erreur est survenue. Veuillez réessayer.') {
  if (!(error instanceof ApiError)) return fallback;
  switch (error.type) {
    case 'network':
      return 'Impossible de joindre le serveur. Vérifiez votre connexion Internet.';
    case 'timeout':
      return 'Le serveur met trop de temps à répondre. Veuillez réessayer.';
    default:
      break;
  }
  if (error.status === 401) return 'Votre session a expiré. Veuillez vous reconnecter.';
  if (error.status === 403) return "Vous n'avez pas les autorisations nécessaires pour cette action.";
  return error.message || fallback;
}

/* ------------------------------------------------------------------ */
/*  Jetons & session                                                   */
/*                                                                     */
/*  Deux supports possibles selon « Rester connecté » :                */
/*    - localStorage (persistant)  → case cochée ;                     */
/*    - sessionStorage (onglet)    → case décochée.                    */
/*  Les jetons ne vivent que dans UN seul store à la fois. La lecture  */
/*  interroge les deux, l'écriture cible le store choisi à la connexion*/
/*  (et le rafraîchissement suit le store où réside déjà la session).  */
/* ------------------------------------------------------------------ */

const AUTH_KEYS = [KEYS.ACCESS_TOKEN, KEYS.REFRESH_TOKEN, KEYS.USER];

/** Store actif : celui qui détient actuellement la session (défaut localStorage). */
function activeStore() {
  const inSession =
    session.get(KEYS.ACCESS_TOKEN) !== null || session.get(KEYS.REFRESH_TOKEN) !== null;
  return inSession ? session : storage;
}

export const getAccessToken = () =>
  storage.get(KEYS.ACCESS_TOKEN) ?? session.get(KEYS.ACCESS_TOKEN);

export const getRefreshToken = () =>
  storage.get(KEYS.REFRESH_TOKEN) ?? session.get(KEYS.REFRESH_TOKEN);

export const getStoredUser = () =>
  storage.get(KEYS.USER) ?? session.get(KEYS.USER);

/**
 * Enregistre une session complète après connexion.
 * @param {Object}  data
 * @param {string}  data.access
 * @param {string}  [data.refresh]
 * @param {Object}  [data.user]
 * @param {boolean} [data.remember] true → localStorage, false → sessionStorage
 */
export function persistSession({ access, refresh, user, remember = false }) {
  const target = remember ? storage : session;
  const other = remember ? session : storage;

  // Une seule source de vérité : on purge l'autre support.
  AUTH_KEYS.forEach((key) => other.remove(key));

  if (access) target.set(KEYS.ACCESS_TOKEN, access);
  if (refresh) target.set(KEYS.REFRESH_TOKEN, refresh);
  if (user) target.set(KEYS.USER, user);
}

/** Met à jour le seul jeton d'accès (rafraîchissement), dans le store actif. */
export function updateAccessToken(access) {
  if (access) activeStore().set(KEYS.ACCESS_TOKEN, access);
}

/** Persiste/rafraîchit l'utilisateur dans le store actif. */
export function setStoredUser(user) {
  if (user) activeStore().set(KEYS.USER, user);
}

/** Efface intégralement les traces de session (déconnexion / échec refresh). */
export function clearSession() {
  AUTH_KEYS.forEach((key) => {
    storage.remove(key);
    session.remove(key);
  });
}

/** Redirige vers la page de connexion en mémorisant la page d'origine. */
export function redirectToLogin() {
  if (window.location.pathname === LOGIN_PAGE) return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.assign(`${LOGIN_PAGE}?next=${next}`);
}

/* ------------------------------------------------------------------ */
/*  Rafraîchissement du jeton (mutualisé — single flight)              */
/* ------------------------------------------------------------------ */

let refreshPromise = null;

/**
 * Demande un nouveau jeton d'accès à partir du refresh token.
 * Les appels concurrents partagent la même promesse pour ne déclencher
 * qu'un seul appel réseau.
 * @returns {Promise<string|null>} le nouveau jeton d'accès, ou null si échec.
 */
function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  const refreshToken = getRefreshToken();
  if (!refreshToken) return Promise.resolve(null);

  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) return null;
      const data = await response.json();
      if (!data?.access_token) return null;
      updateAccessToken(data.access_token);
      return data.access_token;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/* ------------------------------------------------------------------ */
/*  Requête générique                                                  */
/* ------------------------------------------------------------------ */

async function parseBody(response) {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Effectue une requête HTTP vers l'API SIOU.
 *
 * @param {string} path              chemin relatif à l'API (ex. '/auth/login')
 * @param {Object} [options]
 * @param {string} [options.method]  méthode HTTP (défaut 'GET')
 * @param {*}      [options.body]     corps sérialisé en JSON si présent
 * @param {Object} [options.headers] en-têtes additionnels
 * @param {boolean}[options.auth]     joindre le Bearer (défaut true)
 * @param {number} [options.timeout]  délai d'expiration en ms
 * @param {boolean}[options._retry]   usage interne (évite la boucle de refresh)
 * @returns {Promise<*>} le corps JSON de la réponse (ou null)
 * @throws {ApiError}
 */
export async function apiFetch(path, options = {}) {
  const {
    method = 'GET',
    body,
    headers = {},
    auth = true,
    timeout = DEFAULT_TIMEOUT,
    _retry = false,
  } = options;

  const requestHeaders = { ...headers };
  if (body !== undefined) requestHeaders['Content-Type'] = 'application/json';

  if (auth) {
    const token = getAccessToken();
    if (token) requestHeaders.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timer);
    if (error.name === 'AbortError') {
      throw new ApiError('Le serveur met trop de temps à répondre. Réessayez.', {
        type: 'timeout',
      });
    }
    throw new ApiError('Impossible de joindre le serveur. Vérifiez votre connexion.', {
      type: 'network',
    });
  }
  clearTimeout(timer);

  // 401 sur une requête authentifiée → tenter un unique refresh puis rejouer.
  if (response.status === 401 && auth && !_retry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return apiFetch(path, { ...options, _retry: true });
    }
    clearSession();
    redirectToLogin();
    throw new ApiError('Votre session a expiré. Veuillez vous reconnecter.', {
      type: 'auth',
      status: 401,
    });
  }

  const data = await parseBody(response);

  if (!response.ok) {
    const message =
      (data && (data.detail || data.message)) ||
      'Une erreur est survenue. Veuillez réessayer.';
    throw new ApiError(typeof message === 'string' ? message : 'Erreur serveur.', {
      type: response.status >= 500 ? 'http' : 'http',
      status: response.status,
      data,
    });
  }

  return data;
}
