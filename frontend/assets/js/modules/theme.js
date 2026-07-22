/**
 * theme.js
 * Gère la bascule entre thème clair et sombre, avec persistance
 * et respect de la préférence système par défaut.
 */

import { storage, KEYS } from './storage.js';
import { qs, qsa } from './utils.js';

const ATTR = 'data-theme';

function getPreferredTheme() {
  const saved = storage.get(KEYS.THEME);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(theme) {
  document.documentElement.setAttribute(ATTR, theme);
  const isDark = theme === 'dark';

  qsa('[data-theme-toggle]').forEach((el) => {
    if (el.tagName === 'INPUT' && el.type === 'checkbox') {
      el.checked = isDark;
      el.setAttribute('aria-label', isDark ? 'Désactiver le thème sombre' : 'Activer le thème sombre');
    } else {
      el.setAttribute('aria-pressed', isDark ? 'true' : 'false');
      el.setAttribute('aria-label', isDark ? 'Activer le thème clair' : 'Activer le thème sombre');

      // Changer l'icône soleil/lune
      const svg = el.querySelector('svg');
      if (svg) {
        if (isDark) {
          // Icône lune pour le mode sombre
          svg.innerHTML = '<path d="M12 3a6 6 0 0 1 6 6 6 6 0 1 1-12 0 6 6 0 0 1 6-6z" fill="currentColor"/>';
        } else {
          // Icône soleil pour le mode clair
          svg.innerHTML = '<circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>';
        }
      }
    }
  });
}

export function initTheme() {
  applyTheme(getPreferredTheme());

  // Fonction pour attacher les écouteurs d'événements aux boutons theme toggle
  function attachThemeToggleListeners() {
    qsa('[data-theme-toggle]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute(ATTR);
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        storage.set(KEYS.THEME, next);
      });
    });
  }

  // Attacher les écouteurs immédiatement (pour les boutons déjà dans le DOM)
  attachThemeToggleListeners();

  // Réattacher les écouteurs après que les composants dynamiques soient chargés
  document.addEventListener('siou:components-ready', attachThemeToggleListeners);

  // Suit le changement de préférence système si l'utilisateur n'a rien choisi explicitement
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
    if (storage.get(KEYS.THEME) !== null) return;
    applyTheme(event.matches ? 'dark' : 'light');
  });
}
