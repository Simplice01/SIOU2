/**
 * storage.js
 * Petite couche d'abstraction au-dessus du Web Storage.
 * Centralise les clés utilisées par l'application pour éviter les collisions
 * et faciliter une future migration vers une API (FastAPI) sans toucher
 * aux modules appelants.
 *
 * Deux stores partagent la même API et le même namespace :
 *   - `storage` : localStorage — persistance longue durée (thème, session
 *     « Rester connecté »…), survit à la fermeture du navigateur ;
 *   - `session` : sessionStorage — durée de l'onglet, effacé à la fermeture
 *     (session d'authentification non mémorisée).
 */

const NAMESPACE = 'siou';

const KEYS = {
  THEME: 'theme',
  SETTINGS: 'settings',
  SIDEBAR_COLLAPSED: 'sidebar-collapsed',
  CONVERSATIONS: 'conversations',
  DRAFT: 'composer-draft',
  // ---- Authentification ----
  ACCESS_TOKEN: 'auth-access-token',
  REFRESH_TOKEN: 'auth-refresh-token',
  USER: 'auth-user',
};

function buildKey(key) {
  return `${NAMESPACE}:${key}`;
}

/**
 * Construit une façade get/set/remove au-dessus d'un backend Web Storage.
 * @param {() => Storage} getBackend fournit le backend (paresseux, robuste au SSR)
 */
function createStore(getBackend) {
  return {
    get(key, fallback = null) {
      try {
        const raw = getBackend().getItem(buildKey(key));
        return raw === null ? fallback : JSON.parse(raw);
      } catch (error) {
        console.warn(`[storage] Lecture impossible pour "${key}"`, error);
        return fallback;
      }
    },

    set(key, value) {
      try {
        getBackend().setItem(buildKey(key), JSON.stringify(value));
      } catch (error) {
        console.warn(`[storage] Écriture impossible pour "${key}"`, error);
      }
    },

    remove(key) {
      try {
        getBackend().removeItem(buildKey(key));
      } catch (error) {
        console.warn(`[storage] Suppression impossible pour "${key}"`, error);
      }
    },
  };
}

export const storage = createStore(() => window.localStorage);
export const session = createStore(() => window.sessionStorage);

export { KEYS };
