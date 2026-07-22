/**
 * notifications.js
 * Panneau déroulant de notifications (cloche du topbar).
 * Ferme automatiquement au clic extérieur ou à la touche Échap.
 */

import { qs, qsa } from './utils.js';

export function initNotifications() {
  const trigger = qs('[data-notifications-trigger]');
  const panel = qs('[data-notifications-panel]');
  if (!trigger || !panel) return;

  function toggle(forceState) {
    const willOpen = forceState ?? !panel.classList.contains('is-open');
    panel.classList.toggle('is-open', willOpen);
    trigger.setAttribute('aria-expanded', String(willOpen));
  }

  trigger.addEventListener('click', (event) => {
    event.stopPropagation();
    toggle();
  });

  document.addEventListener('click', (event) => {
    if (!panel.contains(event.target)) toggle(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') toggle(false);
  });

  // Marquer tout comme lu
  qs('[data-notifications-mark-read]', panel)?.addEventListener('click', () => {
    qsa('.notification-item.is-unread', panel).forEach((item) => item.classList.remove('is-unread'));
    qs('.icon-btn__dot', trigger)?.remove();
  });
}
