/**
 * route-guard.js
 * Protection des routes côté client.
 *
 * `requireAuth()`  : réservé aux pages privées. Redirige vers /login.html
 *                    (en mémorisant la page demandée) si aucun jeton n'est
 *                    présent. Appelé une seule fois depuis main.js, ce qui
 *                    protège d'un coup toutes les pages qui chargent main.js.
 * `requireGuest()` : réservé à la page de connexion. Renvoie vers l'accueil
 *                    si l'utilisateur est déjà authentifié (évite de revoir
 *                    le formulaire et les boucles de navigation).
 * `requireRole()`  : autorisation par rôle (RBAC), évolutif. Renvoie true si
 *                    l'accès est permis, sinon redirige et renvoie false.
 *
 * Note : ces gardes sont un filtre d'expérience utilisateur, pas une frontière
 * de sécurité. L'autorité reste le backend, qui valide le jeton à chaque
 * requête (Depends(get_current_user) / require_role).
 */

import { isAuthenticated, hasRole, normalizeRole } from './auth.js';

const LOGIN_PAGE = '/login.html';
const HOME_PAGE = '/index.html';
const FLASH_KEY = 'siou:flash';

/** Lit les rôles d'un attribut `data-require-role="a, b"` (liste séparée par virgules). */
function parseRoles(raw) {
  return (raw || '')
    .split(',')
    .map((role) => normalizeRole(role.trim()))
    .filter(Boolean);
}

/** Extrait une cible de redirection sûre depuis `?next=` (chemins internes seuls). */
function safeNextTarget() {
  const next = new URLSearchParams(window.location.search).get('next');
  // On refuse les URL absolues (http://…, //…) pour éviter les redirections ouvertes.
  if (next && next.startsWith('/') && !next.startsWith('//')) return next;
  return HOME_PAGE;
}

/** Page privée : exige une session valide, sinon redirige vers la connexion. */
export function requireAuth() {
  if (isAuthenticated()) return true;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`${LOGIN_PAGE}?next=${next}`);
  return false;
}

/** Page de connexion : renvoie l'utilisateur déjà connecté vers sa destination. */
export function requireGuest() {
  if (!isAuthenticated()) return true;
  window.location.replace(safeNextTarget());
  return false;
}

/**
 * Autorisation par rôle. À utiliser sur les pages/actions réservées.
 * @param {...string} roles rôles autorisés
 * @returns {boolean}
 */
export function requireRole(...roles) {
  if (!requireAuth()) return false;
  if (hasRole(...roles)) return true;
  setFlash('Accès refusé : vous ne disposez pas des autorisations nécessaires.', 'danger');
  window.location.replace(HOME_PAGE);
  return false;
}

/**
 * Applique la restriction de rôle déclarée au niveau de la page :
 *   <body data-require-role="admin, responsable_ministere">
 * Renvoie vers l'accueil (avec message) si le rôle n'est pas autorisé.
 * Appelé une fois depuis main.js → protection par page sans code dédié.
 * @returns {boolean} true si l'accès est permis
 */
export function enforcePageRole() {
  const roles = parseRoles(document.body?.dataset.requireRole);
  if (roles.length === 0 || hasRole(...roles)) return true;
  setFlash('Accès refusé : vous ne disposez pas des autorisations nécessaires.', 'danger');
  window.location.replace(HOME_PAGE);
  return false;
}

/* ------------------------------------------------------------------ */
/*  Message « flash » d'une page à l'autre (survit à une redirection)  */
/* ------------------------------------------------------------------ */

/** Dépose un message à afficher après la prochaine navigation. */
export function setFlash(message, type = 'info') {
  try {
    sessionStorage.setItem(FLASH_KEY, JSON.stringify({ message, type }));
  } catch {
    /* stockage indisponible : on ignore, le message est non essentiel */
  }
}

/** Récupère et consomme le message flash éventuel. */
export function takeFlash() {
  try {
    const raw = sessionStorage.getItem(FLASH_KEY);
    if (!raw) return null;
    sessionStorage.removeItem(FLASH_KEY);
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
