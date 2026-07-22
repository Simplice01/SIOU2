/**
 * sidebar.js
 * Gère l'état rétracté/étendu de la sidebar (bureau) et son ouverture
 * en tiroir sur mobile, avec persistance de la préférence utilisateur.
 */

import { storage, KEYS } from './storage.js';
import { qs } from './utils.js';

export function initSidebar() {
  const shell = qs('.app-shell');
  if (!shell) return;

  const toggleBtn = qs('[data-sidebar-toggle]');
  const mobileMenuBtn = qs('[data-mobile-menu-toggle]');
  const scrim = qs('.sidebar-scrim');

  // ---- Rétractation bureau (persistée) ----
  const collapsed = storage.get(KEYS.SIDEBAR_COLLAPSED, false);
  shell.classList.toggle('is-collapsed', collapsed);

  toggleBtn?.addEventListener('click', () => {
    const isCollapsed = shell.classList.toggle('is-collapsed');
    storage.set(KEYS.SIDEBAR_COLLAPSED, isCollapsed);
    toggleBtn.setAttribute('aria-expanded', String(!isCollapsed));
  });

  // ---- Tiroir mobile ----
  function closeMobileMenu() {
    shell.classList.remove('is-mobile-open');
    mobileMenuBtn?.setAttribute('aria-expanded', 'false');
  }

  mobileMenuBtn?.addEventListener('click', () => {
    const open = shell.classList.toggle('is-mobile-open');
    mobileMenuBtn.setAttribute('aria-expanded', String(open));
  });

  scrim?.addEventListener('click', closeMobileMenu);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeMobileMenu();
  });
}