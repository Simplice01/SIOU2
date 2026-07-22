/**
 * modal.js
 * Ouverture/fermeture accessible des modales déclarées dans le DOM.
 * Déclenchement via [data-modal-open="id"] / [data-modal-close].
 */

import { qs, qsa, trapFocus } from './utils.js';

let lastFocusedElement = null;
let releaseFocusTrap = null;

function openModal(overlay) {
  lastFocusedElement = document.activeElement;
  overlay.classList.add('is-open');
  overlay.setAttribute('aria-hidden', 'false');
  releaseFocusTrap = trapFocus(overlay);

  const firstFocusable = qs(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    overlay
  );
  firstFocusable?.focus();

  document.body.style.overflow = 'hidden';
}

function closeModal(overlay) {
  overlay.classList.remove('is-open');
  overlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  releaseFocusTrap?.();
  lastFocusedElement?.focus();
}

export function initModals() {
  qsa('[data-modal-open]').forEach((trigger) => {
    trigger.addEventListener('click', () => {
      const target = document.getElementById(trigger.dataset.modalOpen);
      if (target) openModal(target);
    });
  });

  qsa('.modal-overlay').forEach((overlay) => {
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeModal(overlay);
    });

    qsa('[data-modal-close]', overlay).forEach((btn) => {
      btn.addEventListener('click', () => closeModal(overlay));
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const openOverlay = qs('.modal-overlay.is-open');
    if (openOverlay) closeModal(openOverlay);
  });
}

export { openModal, closeModal };
