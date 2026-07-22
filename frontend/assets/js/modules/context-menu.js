/**
 * context-menu.js
 * Menus contextuels légers positionnés au clic sur un déclencheur
 * [data-menu-trigger="id"], avec fermeture au clic extérieur / Échap.
 */

import { qs, qsa } from './utils.js';

let openMenu = null;

function closeOpenMenu() {
  if (!openMenu) return;
  openMenu.classList.remove('is-open');
  openMenu = null;
}

function positionMenu(menu, trigger) {
  const rect = trigger.getBoundingClientRect();
  const menuWidth = menu.offsetWidth || 190;
  const spaceRight = window.innerWidth - rect.right;

  menu.style.top = `${rect.bottom + window.scrollY + 4}px`;
  menu.style.left =
    spaceRight < menuWidth
      ? `${rect.right + window.scrollX - menuWidth}px`
      : `${rect.left + window.scrollX}px`;
}

export function initContextMenus() {
  qsa('[data-menu-trigger]').forEach((trigger) => {
    const menu = document.getElementById(trigger.dataset.menuTrigger);
    if (!menu) return;

    trigger.addEventListener('click', (event) => {
      event.stopPropagation();
      const isSameMenu = openMenu === menu;
      closeOpenMenu();
      if (!isSameMenu) {
        positionMenu(menu, trigger);
        menu.classList.add('is-open');
        openMenu = menu;
      }
    });
  });

  document.addEventListener('click', closeOpenMenu);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeOpenMenu();
  });
  window.addEventListener('resize', closeOpenMenu);
}
