/**
 * toast.js
 * Système de notifications toast, empilées en bas à droite.
 * API : showToast({ title, text, type, duration })
 */

import { createEl, uid } from './utils.js';

const ICONS = {
  success:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>',
  warning:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4M12 17h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>',
  danger:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
};

let region;

function ensureRegion() {
  if (region) return region;
  region = document.querySelector('.toast-region');
  if (!region) {
    region = createEl('div', {
      class: 'toast-region',
      role: 'status',
      'aria-live': 'polite',
    });
    document.body.appendChild(region);
  }
  return region;
}

/**
 * Affiche une notification toast.
 * @param {Object} options
 * @param {string} options.title
 * @param {string} [options.text]
 * @param {'success'|'warning'|'danger'|'info'} [options.type]
 * @param {number} [options.duration] en ms, 0 pour persistant
 */
export function showToast({ title, text = '', type = 'info', duration = 4500 }) {
  const container = ensureRegion();
  const id = uid('toast');

  const toast = createEl('div', {
    class: `toast toast--${type}`,
    id,
    role: 'alert',
  });

  toast.innerHTML = `
    <span class="toast__icon">${ICONS[type] || ICONS.info}</span>
    <div>
      <p class="toast__title">${title}</p>
      ${text ? `<p class="toast__text">${text}</p>` : ''}
    </div>
    <button class="toast__close" aria-label="Fermer la notification">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
    </button>
  `;

  const remove = () => {
    toast.classList.add('is-leaving');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  toast.querySelector('.toast__close').addEventListener('click', remove);
  container.appendChild(toast);

  if (duration > 0) setTimeout(remove, duration);

  return { id, remove };
}
