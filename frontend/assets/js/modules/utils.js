/**
 * utils.js
 * Fonctions utilitaires partagées par tous les modules SIOU.
 * Aucune dépendance externe — ES modules natifs.
 */

/**
 * Retarde l'exécution d'une fonction tant qu'elle est rappelée
 * (utilisé pour la recherche instantanée).
 * @param {Function} fn
 * @param {number} delay en ms
 */
export function debounce(fn, delay = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Sélecteur court, portée par défaut : document.
 * @param {string} selector
 * @param {ParentNode} [scope]
 */
export const qs = (selector, scope = document) => scope.querySelector(selector);

/**
 * Sélecteur multiple retournant un tableau (et non une NodeList).
 * @param {string} selector
 * @param {ParentNode} [scope]
 */
export const qsa = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

/**
 * Crée un élément DOM avec attributs et enfants en une seule fois.
 * @param {string} tag
 * @param {Object} attrs
 * @param {Array<Node|string>} children
 */
export function createEl(tag, attrs = {}, children = []) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') el.className = value;
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value !== null && value !== undefined) {
      el.setAttribute(key, value);
    }
  }
  children.forEach((child) => {
    el.append(child instanceof Node ? child : document.createTextNode(child));
  });
  return el;
}

/**
 * Formate une date en français relatif (ex : "Aujourd'hui", "Hier", "12 juin").
 * @param {Date|string} input
 */
export function formatRelativeDate(input) {
  const date = new Date(input);
  const now = new Date();
  const diffDays = Math.floor((startOfDay(now) - startOfDay(date)) / 86400000);

  if (diffDays === 0) return "Aujourd'hui";
  if (diffDays === 1) return 'Hier';
  if (diffDays < 7) return `Il y a ${diffDays} jours`;

  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
}

function startOfDay(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

/**
 * Formate une heure au format HH:MM (fr-FR).
 * @param {Date|string} input
 */
export function formatTime(input) {
  return new Date(input).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Génère un identifiant court unique côté client (non cryptographique).
 */
export function uid(prefix = 'id') {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Échappe le HTML pour l'insertion sûre de texte utilisateur.
 * @param {string} str
 */
export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Limite une valeur entre min et max.
 */
export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/**
 * Piège le focus clavier à l'intérieur d'un conteneur (accessibilité modales).
 * @param {HTMLElement} container
 * @returns {Function} fonction de nettoyage (removeEventListener)
 */
export function trapFocus(container) {
  const focusableSelector =
    'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

  function handleKeydown(event) {
    if (event.key !== 'Tab') return;
    const focusable = qsa(focusableSelector, container).filter((el) => el.offsetParent !== null);
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  container.addEventListener('keydown', handleKeydown);
  return () => container.removeEventListener('keydown', handleKeydown);
}
